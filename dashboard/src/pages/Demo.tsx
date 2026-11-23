import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchInventories, type MCPInventory } from '../api';

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

  return <div>
    <header style={{ padding: '56px 0 28px', maxWidth: 760 }}><span className="eyebrow">Agent workspace</span>
      <h1>Run a task</h1><p className="sub">Enter a task to discover relevant tools from approved MCP servers. CrossToolGuard checks each call and records the evidence.</p></header>
    <div className="card" style={{ padding: 22, display: 'grid', gap: 16 }}>
      {catalogError ? <p role="alert">{catalogError}</p> : !catalog ? <p role="status">Loading approved servers…</p>
        : catalog.length === 0 && <p>No approved servers. <Link to="/inventory">Review and approve an inventory</Link>.</p>}
      {approvedServers.length > 0 && <details><summary>{approvedServers.reduce((sum, item) => sum + item.tools.length, 0)} approved tools across {approvedServers.length} servers</summary>
        {approvedServers.map((item) => <p key={item.server_id}>{item.server_id}: {item.tools.map((tool) => tool.name).join(', ')}</p>)}
      </details>}
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
      <div><label htmlFor="agent-task">Task</label><textarea id="agent-task" value={task} onChange={(e) => setTask(e.target.value)} placeholder="For example: Find invoice INV-1042 and summarize its total and status." rows={3} style={{ display: 'block', width: '100%', marginTop: 6 }} /></div>
      <label>Model provider<br /><select value={provider} onChange={(e) => { setProvider(e.target.value); setModel(''); }}>
        {providers.map((item) => <option key={item.id} value={item.id} disabled={!item.configured}>{item.id}{item.configured ? '' : ' (not configured)'}</option>)}
      </select></label>
      <label>Model<br /><select value={model} onChange={(e) => setModel(e.target.value)}><option value="">Provider default</option>
        {(providers.find((item) => item.id === provider)?.models ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
      </select></label>
      <label>Agent policy<br /><select value={policy} onChange={(e) => setPolicy(e.target.value)}><option value="hardened">Hardened</option><option value="baseline">Baseline</option></select></label>
      <p style={{ color: 'var(--muted)', fontSize: 13 }}>Approved tool descriptions, your task, and returned tool data go to the model provider. Use test data and review approved inventories before running.</p>
      <button className="btn-primary" disabled={!task.trim() || Boolean(catalogError) || !approvedServers.length || (manualScope && !selectedServers.length) || status === 'starting' || status === 'running' || status === 'awaiting_approval'} onClick={start}>Run task</button>
    </div>
    {error && <p role="alert" style={{ color: 'var(--crit)' }}>{error}</p>}
    {session && <section style={{ marginTop: 24 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0 }}>Session {session}</h2>
        <button style={{ marginLeft: 'auto' }} onClick={() => { setTask(''); setSession(''); setStatus(''); setReport(null); setAnswer(''); setPending([]); setError(''); setParams({}); }}>Start another run</button>
      </div>
      <p>Status: {status} · {toolCount} candidate tools{availableToolCount > toolCount ? ` out of ${availableToolCount} approved` : ''}</p>
      {pending.map((item) => <div key={item.id} className="card" style={{ padding: 16, marginBottom: 12 }}>
        <strong>Approval required: {item.server}/{item.tool}</strong>
        <p>Argument fields: {item.argument_fields?.join(', ') || 'none'} · Data class: {item.data_class ?? 'unknown'}</p>
        {item.reason && <p>{item.reason}</p>}
        <p>Destination: {item.destination_label ?? 'No reviewed destination recorded'}</p>
        {item.arguments_sha256 && <p className="mono">Argument hash: {item.arguments_sha256.slice(0, 16)}</p>}
        <p>Expires {new Date(item.expires_at * 1000).toLocaleTimeString()}. The agent will resume only if you grant this exact call.</p>
        <button onClick={() => decide(item, true)}>Grant once</button> <button onClick={() => decide(item, false)}>Deny</button>
      </div>)}
      {report && <><p>Result: {report.outcome} · {report.halted_reason}</p>
        <p className="mono" style={{ color: 'var(--muted)', fontSize: 12 }}>{report.provider ?? 'provider'} · {report.model ?? 'model'} · {report.policy ?? 'policy'}</p>
        {runExplanation(report.halted_reason) && <p role="status">{runExplanation(report.halted_reason)}</p>}
        {answer && <div className="card" style={{ padding: 16, whiteSpace: 'pre-wrap' }}><strong>Agent answer</strong><p>{answer}</p></div>}
        <ol>{report.calls.map((call, index) => <li key={`${call.tool}-${index}`} className="mono">{call.tool} → {call.verdict ?? 'ERROR'}</li>)}</ol>
        <p>ALLOW on a legitimate call does not mean an attack was blocked. Inspect the graph for observed paths and possible harm paths.</p></>}
      <Link to={`/graph?session=${encodeURIComponent(session)}`}>Open this session's graph →</Link>
      {' · '}
      <Link to="/findings">Open findings →</Link>
    </section>}
  </div>;
}
