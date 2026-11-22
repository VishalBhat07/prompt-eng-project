import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RiskMeter, SeverityBadge } from '../components/Severity';
import { listSessions } from '../data/provider';

interface Finding { session: string; pattern: string; severity: 'CRITICAL' | 'HIGH'; risk: number; tools: string[]; explanation: string; verdict: string }
interface Potential { session: string; source: string; destination: string; explanation: string; trigger_events: { tool: string }[] }
interface Signal { session: string; node_id: string; origin_tool: string; explanation: string }

export default function Findings() {
  const [rows, setRows] = useState<Finding[]>([]);
  const [possible, setPossible] = useState<Potential[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
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
        const body = await response.json() as { alerts?: Omit<Finding, 'session'>[]; potential_paths?: Omit<Potential, 'session'>[]; signals?: Omit<Signal, 'session'>[] };
        return { observed: (body.alerts ?? []).map((item) => ({ ...item, session: id })),
          possible: (body.potential_paths ?? []).map((item) => ({ ...item, session: id })),
          signals: (body.signals ?? []).map((item) => ({ ...item, session: id })) };
      }));
      if (active) {
        const available = results.flatMap((result) => result.status === 'fulfilled' ? [result.value] : []);
        setRows(available.flatMap((item) => item.observed));
        setPossible(available.flatMap((item) => item.possible));
        setSignals(available.flatMap((item) => item.signals));
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
    <section style={{ borderTop: '1px solid var(--line)', paddingTop: 18 }}>
      <h2>Observed attack paths <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· {rows.length}</span></h2>
      <p>Completed graph findings from live and saved sessions. A path is shown only when the observed events matched a configured pattern.</p>
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
