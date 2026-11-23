import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RiskMeter, SeverityBadge } from '../components/Severity';
import { listSessions } from '../data/provider';

interface Finding { session: string; pattern: string; severity: 'CRITICAL' | 'HIGH'; risk: number; tools: string[]; explanation: string; verdict: string }
interface Potential { session: string; source: string; destination: string; explanation: string; trigger_events: { tool: string }[] }
interface Signal { session: string; node_id: string; origin_tool: string; explanation: string }
interface BlockEvidence { policy: string; pattern: string; node_ids: string[]; tools: string[]; data_classes: string[]; capabilities: string[] }
interface Block { id: string; session: string; server: string; tool: string; reason: string; check: string; evidence: BlockEvidence[]; call_node_id: string | null }

function blockGraph(block: Block) {
  const params = new URLSearchParams({ session: block.session });
  const ids = new Set([block.call_node_id, ...block.evidence.flatMap((item) => item.node_ids)]);
  ids.forEach((id) => { if (id) params.append('focus', id); });
  return `/graph?${params}`;
}

export default function Findings() {
  const [rows, setRows] = useState<Finding[]>([]);
  const [possible, setPossible] = useState<Potential[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [severity, setSeverity] = useState('ALL');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(0);
  useEffect(() => {
    let active = true;
    const refresh = () => listSessions().then(async (sessions) => {
      const results = await Promise.allSettled(sessions.map(async ({ id }) => {
        const response = await fetch(`/api/sessions/${encodeURIComponent(id)}`);
        if (!response.ok) throw new Error(`Session ${id} could not be loaded`);
        const body = await response.json() as { alerts?: Omit<Finding, 'session'>[]; potential_paths?: Omit<Potential, 'session'>[]; signals?: Omit<Signal, 'session'>[]; blocks?: Omit<Block, 'session'>[] };
        return { observed: (body.alerts ?? []).map((item) => ({ ...item, session: id })),
          possible: (body.potential_paths ?? []).map((item) => ({ ...item, session: id })),
          signals: (body.signals ?? []).map((item) => ({ ...item, session: id })),
          blocks: (body.blocks ?? []).map((item) => ({ ...item, session: id })) };
      }));
      if (active) {
        const available = results.flatMap((result) => result.status === 'fulfilled' ? [result.value] : []);
        setRows(available.flatMap((item) => item.observed));
        setPossible(available.flatMap((item) => item.possible));
        setSignals(available.flatMap((item) => item.signals));
        setBlocks(available.flatMap((item) => item.blocks));
        setMissing(results.length - available.length);
        setError('');
      }
    }).catch((e: Error) => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  return <div>
    <header style={{ padding: '56px 0 28px', maxWidth: 720 }}><span className="eyebrow">Review</span>
      <h1>Findings</h1><p className="sub">Graph findings from recorded and live sessions.</p></header>
    {error && <p role="alert">{error}</p>}
    {loading && <p role="status">Loading session findings…</p>}
    {missing > 0 && <p role="status">{missing} session(s) could not be loaded. Counts below cover the available sessions.</p>}
    <section style={{ borderTop: '1px solid var(--line)', paddingTop: 18, marginBottom: 26 }}>
      <h2>Blocked calls · {blocks.length}</h2>
      {!loading && !error && !missing && blocks.length === 0 && <p>No call-level block explanations recorded.</p>}
      {blocks.map((item) => <details className="card" key={`${item.session}-${item.id}`} style={{ padding: 14, marginBottom: 8 }}>
        <summary style={{ cursor: 'pointer', overflowWrap: 'anywhere' }}>
          <strong>BLOCK · {item.server}/{item.tool}</strong> · Why was this blocked?
        </summary>
        <p>{item.reason} The gateway stopped the proposed call before invoking the tool.</p>
        {item.evidence.map((evidence, index) => <div key={index}>
          <p><strong>Rule:</strong> {evidence.policy} · <strong>Matched pattern:</strong> {evidence.pattern}</p>
          <p>{evidence.tools.join(' → ')}</p>
          {evidence.data_classes.length > 0 && <p>Data labels: {evidence.data_classes.join(', ')}</p>}
          {evidence.capabilities.length > 0 && <p>Capabilities: {evidence.capabilities.join(', ')}</p>}
        </div>)}
        {(item.call_node_id || item.evidence.length > 0) && <Link to={blockGraph(item)}>Inspect evidence in graph →</Link>}
      </details>)}
    </section>
    <section style={{ borderTop: '1px solid var(--line)', paddingTop: 18 }}>
      <h2>Observed attack paths <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· {rows.length}</span></h2>
      <p>Patterns matched in session events. The policy assessment here describes the path. Recorded call decisions appear under Blocked calls.</p>
    </section>
    <div style={{ display: 'flex', gap: 8, margin: '12px 0 18px' }}>{['ALL', 'CRITICAL', 'HIGH'].map((value) =>
      <button key={value} onClick={() => setSeverity(value)} style={{ borderColor: severity === value ? 'var(--accent)' : undefined }}>{value}</button>)}</div>
    {rows.filter((item) => severity === 'ALL' || item.severity === severity).map((item, index) =>
      <article key={`${item.session}-${item.pattern}-${index}`} style={{ padding: '20px 0', borderTop: '1px solid var(--line)' }}>
        <SeverityBadge level={item.severity} /> <strong className="mono">{item.pattern}</strong> <RiskMeter score={item.risk} />
        <p className="mono">{item.tools.join(' → ')}</p>
        <p>{item.explanation}</p>
        <Link to={`/graph?session=${encodeURIComponent(item.session)}`}>Open {item.session} graph →</Link>
      </article>)}
    {!loading && !error && !missing && rows.length === 0 && <p>No attack paths detected in recorded sessions.</p>}
    <section style={{ marginTop: 32, borderTop: '1px solid var(--line)', paddingTop: 20 }}>
      <h2>Suspicious tool output observed <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· {signals.length}</span></h2>
      <p>An untrusted result contained an instruction-like command. This does not mean the agent followed it.</p>
      {signals.map((item) => <article key={`${item.session}-${item.node_id}`} style={{ padding: '12px 0' }}>
        <strong style={{ color: 'var(--crit)' }}>{item.origin_tool}</strong><p>{item.explanation}</p>
        <Link to={`/graph?session=${encodeURIComponent(item.session)}`}>View observed signal in graph →</Link>
      </article>)}
      {!loading && !error && !missing && signals.length === 0 && <p>No suspicious tool-output signals in recorded sessions.</p>}
    </section>
    <section style={{ marginTop: 32, borderTop: '1px solid var(--line)', paddingTop: 20 }}>
      <h2>Possible harm paths <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· {possible.length}</span></h2>
      <p>Capability-based hypotheses. These are not observed attacks or policy blocks.</p>
      {possible.map((item, index) => <article key={`${item.session}-${index}`} style={{ padding: '12px 0' }}>
        <p className="mono">{item.source} → {item.destination}</p>
        <p>{item.explanation}</p>
        {item.trigger_events.length > 0 && <p>Untrusted output observed from {item.trigger_events.map((event) => event.tool).join(', ')}</p>}
        <Link to={`/graph?session=${encodeURIComponent(item.session)}`}>View possible path in graph →</Link>
      </article>)}
      {!loading && !error && !missing && possible.length === 0 && <p>No possible paths identified in recorded sessions.</p>}
    </section>
  </div>;
}
