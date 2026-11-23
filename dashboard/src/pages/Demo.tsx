import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchInventories, type MCPInventory } from '../api';
import './Demo.css';

interface RunReport {
  session_id: string; outcome: string; halted_reason: string; provider?: string; model?: string; policy?: string;
  calls: { tool: string; verdict?: string }[];
}
interface Pending { id: string; session: string; server: string; tool: string; expires_at: number; argument_fields?: string[]; arguments_sha256?: string; data_class?: string; reason?: string; destination_label?: string | null }

function runExplanation(reason: string) {
  if (reason.includes('rate_limit')) return 'The model provider reached a usage or token limit. Select fewer servers, retry after a minute, or choose another configured model.';
  if (reason.includes('model_or_parse_error')) return 'The model request failed or returned an invalid action. This is a run error, not an attack finding.';
  if (reason.includes('guarded_call_error')) return 'An MCP connection or gateway request failed. Check the server is running and its inventory is current.';
  if (reason === 'step_budget_exhausted') return 'The run reached its step limit before completing. Try a smaller task.';
  if (reason === 'approval_denied_or_expired') return 'The sensitive action was not executed because approval was denied or expired.';
  if (reason === 'guarded_call_block') return 'CrossToolGuard stopped a proposed call. Inspect the graph for the evidence.';
  return '';
}

export default function Demo() {
  const [params, setParams] = useSearchParams();
  const [task, setTask] = useState('');
  const [provider, setProvider] = useState('groq');
  const [model, setModel] = useState('');
  const [policy, setPolicy] = useState('hardened');
  const [providers, setProviders] = useState<{ id: string; configured: boolean; models: string[] }[]>([]);
  const [session, setSession] = useState(params.get('session') ?? '');
  const [status, setStatus] = useState(params.has('session') ? 'running' : '');
  const [toolCount, setToolCount] = useState(0);
  const [availableToolCount, setAvailableToolCount] = useState(0);
  const [manualScope, setManualScope] = useState(false);
  const [report, setReport] = useState<RunReport | null>(null);
  const [answer, setAnswer] = useState('');
  const [pending, setPending] = useState<Pending[]>([]);
  const [error, setError] = useState('');
  const [catalog, setCatalog] = useState<MCPInventory[] | null>(null);
  const [catalogError, setCatalogError] = useState('');
  const [selectedServers, setSelectedServers] = useState<string[]>([]);
  useEffect(() => {
    let active = true;
    let firstLoad = true;
    const refresh = async () => {
      try {
        const approved = (await fetchInventories()).filter((item) => item.integrity_status === 'APPROVED');
        if (!active) return;
        const ids = new Set(approved.map((item) => item.server_id));
        if (firstLoad) {
          const local = ['fixture-invoice', 'fixture-file', 'fixture-send'].filter((id) => ids.has(id));
          setSelectedServers(local.length ? local : [...ids]);
          firstLoad = false;
        } else {
          setSelectedServers((current) => current.filter((id) => ids.has(id)));
        }
        setCatalog(approved);
        setCatalogError('');
      } catch {
        if (active) setCatalogError('Could not load approved servers. The dashboard will retry.');
      }
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const approvedServers = catalog ?? [];
  const approvedTools = approvedServers.reduce((total, server) => total + server.tools.length, 0);
  const busy = ['starting', 'running', 'awaiting_approval'].includes(status);
  const canRun = Boolean(task.trim() && !catalogError && approvedServers.length
    && (!manualScope || selectedServers.length) && !busy
    && providers.find((item) => item.id === provider)?.configured !== false);
  const runStatus = status === 'awaiting_approval' ? 'Waiting for approval' :
    status === 'starting' ? 'Starting' : status === 'running' ? 'Running' :
    report?.outcome === 'COMPLETED' ? 'Completed' : report?.outcome === 'BLOCKED' ? 'Blocked' :
    report?.outcome === 'INCOMPLETE' ? 'Incomplete' :
    status === 'error' || report?.outcome === 'ERROR' ? 'Run error' : status === 'complete' ? 'Finished' : 'Ready';

  useEffect(() => { fetch('/api/llm/providers').then((r) => r.json()).then((body) => setProviders(body.providers ?? [])).catch(() => {}); }, []);
  useEffect(() => {
    if (!session || status === 'complete' || status === 'error') return;
    const poll = async () => {
      try {
        const response = await fetch(`/api/mcp/agent/runs/${encodeURIComponent(session)}`);
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? `Status failed (${response.status})`);
        setStatus(body.status);
        if (body.approved_tool_count) setToolCount(body.approved_tool_count);
        if (body.available_tool_count) setAvailableToolCount(body.available_tool_count);
        if (body.report) setReport(body.report);
        if (typeof body.answer === 'string') setAnswer(body.answer);
        if (body.error) setError(body.error);
        if (body.status === 'awaiting_approval') {
          const approvalResponse = await fetch('/api/approvals');
          if (approvalResponse.ok) {
            const approvals = await approvalResponse.json();
            setPending((approvals.pending ?? []).filter((item: Pending) => item.session === session));
          }
        } else setPending([]);
      } catch (e) { setError(e instanceof Error ? e.message : 'Status failed'); }
    };
    void poll();
    const timer = window.setInterval(() => { void poll(); }, 1500);
    return () => window.clearInterval(timer);
  }, [session, status]);

  const start = async () => {
    if (!canRun) return;
    setError(''); setReport(null); setAnswer(''); setSession(''); setPending([]); setStatus('starting');
    try {
      const response = await fetch('/api/mcp/agent/run', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, provider, model: model || undefined, policy, auto_discover: true,
          server_ids: manualScope ? selectedServers : undefined }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? `Run failed (${response.status})`);
      setToolCount(body.approved_tool_count); setSession(body.session_id); setStatus(body.status);
      setAvailableToolCount(body.available_tool_count);
      setParams({ session: body.session_id });
    } catch (e) { setError(e instanceof Error ? e.message : 'Run failed'); setStatus('error'); }
  };

  const decide = async (approval: Pending, grant: boolean) => {
    try {
      const response = await fetch(grant ? '/api/approvals/grant' : `/api/approvals/${encodeURIComponent(approval.id)}/deny`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: grant ? JSON.stringify({ approval_id: approval.id }) : '{}',
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? 'Approval decision failed');
      setPending((items) => items.filter((item) => item.id !== approval.id));
    } catch (e) { setError(e instanceof Error ? e.message : 'Approval decision failed'); }
  };

  return <div className="demo-page">
    <header className="demo-heading">
      <h1>Run a task</h1><p className="sub">Describe what you need. The agent chooses tools from your approved MCP servers.</p>
    </header>
    <div className="demo-workspace">
    <form className="card demo-composer" onSubmit={(event) => { event.preventDefault(); void start(); }}>
      <div><label className="demo-label" htmlFor="agent-task">Task</label>
        <textarea id="agent-task" value={task} onChange={(e) => setTask(e.target.value)}
          placeholder="Find invoice INV-1042 and summarize its total and status." rows={4} />
      </div>
      {catalogError ? <p role="alert">{catalogError}</p> : !catalog ? <p role="status">Loading approved servers…</p>
        : catalog.length === 0 && <p>No approved servers. <Link to="/inventory">Review and approve an inventory</Link>.</p>}
      <details className="demo-settings">
        <summary>Run settings <span>{provider} · {policy}</span></summary>
        <div className="demo-settings-body">
        <div className="demo-settings-grid">
          <label>Model provider<select value={provider} onChange={(e) => { setProvider(e.target.value); setModel(''); }}>
            {!providers.length && <option value={provider}>{provider}</option>}
            {providers.map((item) => <option key={item.id} value={item.id} disabled={!item.configured}>{item.id}{item.configured ? '' : ' (not configured)'}</option>)}
          </select></label>
          <label>Model<select value={model} onChange={(e) => setModel(e.target.value)}><option value="">Provider default</option>
            {(providers.find((item) => item.id === provider)?.models ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select></label>
          <label>Agent policy<select value={policy} onChange={(e) => setPolicy(e.target.value)}><option value="hardened">Hardened</option><option value="baseline">Baseline</option></select></label>
        </div>
      <label><input type="checkbox" checked={manualScope} onChange={(event) => setManualScope(event.target.checked)} /> Limit discovery to selected servers</label>
      {manualScope && <fieldset disabled={!approvedServers.length || Boolean(catalogError)} style={{ border: '1px solid var(--line)', borderRadius: 8, padding: 12 }}>
        <legend>Servers for this run ({selectedServers.length}/{approvedServers.length})</legend>
        <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 0 }}>
          Choose the servers needed for the task. Smaller catalogs use less model context.
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <button type="button" onClick={() => setSelectedServers(approvedServers.map((item) => item.server_id))}>Select all</button>
          <button type="button" onClick={() => setSelectedServers([])}>Clear</button>
        </div>
        <div style={{ display: 'grid', gap: 6 }}>
          {approvedServers.map((item) => <label key={item.server_id} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
            <input type="checkbox" checked={selectedServers.includes(item.server_id)}
              onChange={(e) => setSelectedServers((current) => e.target.checked
                ? [...current, item.server_id]
                : current.filter((serverId) => serverId !== item.server_id))} />
            <span className="mono">{item.server_id}</span>
            <span style={{ color: 'var(--muted)', fontSize: 12 }}>{item.tools.length} tools</span>
          </label>)}
        </div>
      </fieldset>}
        </div>
      </details>
      <p className="demo-note">Your task and returned tool data are shared with the selected model provider.</p>
      <div className="demo-actions">
        <Link to="/inventory">{approvedTools} approved tools · {approvedServers.length} servers</Link>
        <button className="btn-primary" type="submit" disabled={!canRun}>
          {status === 'awaiting_approval' ? 'Waiting for approval' :
            status === 'starting' ? 'Starting…' : status === 'running' ? 'Running…' : 'Run task'}
        </button>
      </div>
    {error && <p role="alert" style={{ color: 'var(--crit)' }}>{error}</p>}
    </form>
    <section className="card demo-output" aria-label="Task result">
      <div className="demo-result-head">
        <h2>Run result</h2>
        <span className="demo-state" data-state={status} role="status">{runStatus}</span>
      </div>
      {!session && !busy && <p className="demo-note">Run a task to see the agent’s answer and tool decisions here.</p>}
      {session && <>
      <p className="demo-note">{toolCount} candidate tools{availableToolCount > toolCount ? ` out of ${availableToolCount} approved` : ''}</p>
      {status === 'awaiting_approval' && pending.length === 0 && <p role="status">Loading approval request…</p>}
      {pending.map((item) => <div key={item.id} className="demo-approval">
        <strong>Approval required: {item.server}/{item.tool}</strong>
        <p>Argument fields: {item.argument_fields?.join(', ') || 'none'} · Data class: {item.data_class ?? 'unknown'}</p>
        {item.reason && <p>{item.reason}</p>}
        <p>Destination: {item.destination_label ?? 'No reviewed destination recorded'}</p>
        {item.arguments_sha256 && <p className="mono">Argument hash: {item.arguments_sha256.slice(0, 16)}</p>}
        <p>Expires {new Date(item.expires_at * 1000).toLocaleTimeString()}. The agent will resume only if you grant this exact call.</p>
        <div className="demo-decision"><button className="btn-primary" onClick={() => decide(item, true)}>Grant once</button><button onClick={() => decide(item, false)}>Deny</button></div>
      </div>)}
      {report && <>
        {runExplanation(report.halted_reason) && <p role="status">{runExplanation(report.halted_reason)}</p>}
        {answer && <div className="demo-answer"><h3>Agent answer</h3><p>{answer}</p></div>}
        {report.calls.length > 0 && <div><h3>Tool calls</h3><ol className="demo-calls">
          {report.calls.map((call, index) => <li key={`${call.tool}-${index}`}>
            <span>{call.tool}</span><strong data-verdict={call.verdict}>{call.verdict ?? 'ERROR'}</strong>
          </li>)}</ol></div>}
        <details className="demo-settings"><summary>Run details</summary>
          <p className="demo-note">{report.provider ?? provider} · {report.model ?? 'Provider default'} · {report.policy ?? policy}</p>
          <p className="demo-note">{report.outcome} · {report.halted_reason}</p>
          <p className="demo-note mono">{session}</p>
        </details>
      </>}
      <div className="demo-result-links">
        <Link to={`/graph?session=${encodeURIComponent(session)}`}>Open this session's graph →</Link>
        <Link to="/findings">Open findings →</Link>
      </div>
      {!busy && <button className="demo-reset" onClick={() => { setTask(''); setSession(''); setStatus(''); setReport(null); setAnswer(''); setPending([]); setError(''); setParams({}); }}>Start another run</button>}
      </>}
    </section>
    </div>
  </div>;
}
