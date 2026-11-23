import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { BenchDoc } from '../data/types';
import BenchmarkComparison from '../components/BenchmarkComparison';

const TIP = { background: 'var(--bg-1)', border: '1px solid var(--line)', fontSize: 13, color: 'var(--ink)' };
// SVG attributes (ticks, grid) can't use var(); fixed mid-gray reads on both themes.
const AXIS = { fill: '#888888', fontSize: 12 };
const GRID = 'rgba(128,128,128,0.25)';

interface Rate { numerator: number; denominator: number }
interface EvaluationResults {
  replay: Record<string, { alert_recall: Rate; false_alerts: Rate }>;
  benign: Record<string, { completion: Rate; candidate_recall: Rate; errors: Record<string, number> }>;
  model: { provider: string; model: string };
}
const count = (rate: Rate) => `${rate.numerator} / ${rate.denominator}`;

export default function Benchmark() {
  const [d, setD] = useState<BenchDoc | null>(null);
  const [runs, setRuns] = useState<{ session_id: string; outcome: string; policy: string; provider: string; model: string; calls: { tool: string; verdict?: string }[] }[]>([]);
  const [table, setTable] = useState(false);
  const [runsError, setRunsError] = useState('');
  const [evaluation, setEvaluation] = useState<EvaluationResults>();
  const [evaluationError, setEvaluationError] = useState(false);
  const loadRuns = () => fetch('/api/runs').then((r) => r.json())
    .then((body) => { setRuns(body.runs ?? []); setRunsError(''); })
    .catch(() => setRunsError('Could not load recorded runs from the gateway.'));
  useEffect(() => { fetch('/data/benchmark.json').then((r) => r.json()).then(setD).catch(() => {}); }, []);
  useEffect(() => { void loadRuns(); }, []);
  useEffect(() => {
    fetch('/data/evaluation-results-v1.json').then((response) => {
      if (!response.ok) throw new Error('Evaluation unavailable');
      return response.json();
    }).then(setEvaluation).catch(() => setEvaluationError(true));
  }, []);
  if (!d) return <p style={{ color: 'var(--faint)' }}>Loading benchmark.json…</p>;
  const baseRows = Object.entries(d.baselines).map(([k, v]) => ({ name: k, caught: v.caught }));
  const ablRows = Object.entries(d.ablation).map(([k, v]) => ({ name: k.replace('-', ' +'), caught: v.caught }));
  return (
    <div>
      <header style={{ padding: '56px 0 28px', maxWidth: 720 }}>
        <span className="eyebrow">Evidence</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Benchmark</h1>
        <p className="sub" style={{ fontSize: 16 }}>
          Synthetic trace benchmark: {d.cases} cases ({d.attack_cases ?? 8} attack, {d.cases - (d.attack_cases ?? 8)} integrity/provenance/no-finding) · detection {Math.round(d.detection_rate * 100)}% · FPR {Math.round(d.false_positive_rate * 100)}%. Recorded model runs are listed separately below.
        </p>
      </header>
      <BenchmarkComparison />
      {evaluationError && <p role="alert">The research summary could not be loaded.</p>}
      {evaluation && <section style={{ marginBottom: 32 }}>
        <h2>Replay pilot · 24 synthetic records</h2>
        <div style={{ overflowX: 'auto' }}><table>
          <thead><tr><th>Method</th><th>Positive records flagged</th><th>False alerts</th></tr></thead>
          <tbody>{Object.entries(evaluation.replay).map(([method, result]) =>
            <tr key={method}><td>{method.replace(/_/g, ' ')}</td><td>{count(result.alert_recall)}</td><td>{count(result.false_alerts)}</td></tr>)}</tbody>
        </table></div>
        <h2>Benign agent comparison · 48 scheduled trials</h2>
        <p>{evaluation.model.provider} · {evaluation.model.model} · local read-only tools</p>
        <div style={{ overflowX: 'auto' }}><table>
          <thead><tr><th>Scope</th><th>Completed</th><th>Required tools available</th><th>Provider errors</th></tr></thead>
          <tbody>{Object.entries(evaluation.benign).map(([scope, result]) =>
            <tr key={scope}><td>{scope.replace(/_/g, ' ')}</td><td>{count(result.completion)}</td>
              <td>{count(result.candidate_recall)}</td><td>{Object.values(result.errors).reduce((sum, n) => sum + n, 0)}</td></tr>)}</tbody>
        </table></div>
      </section>}
      <div style={{ display: 'flex', gap: 12, padding: '12px 0', borderTop: '1px solid var(--line)' }}>
        <button style={{ fontSize: 13 }} onClick={() => setTable((t) => !t)}>{table ? 'View as charts' : 'View as table'}</button>
        <a href="/data/benchmark.json" download style={{ fontSize: 13.5, color: 'var(--accent)', textDecoration: 'none' }}>Download JSON</a>
      </div>
      {table ? (
        <div className="mono" style={{ fontSize: 13.5, color: 'var(--muted)', lineHeight: 2, borderTop: '1px solid var(--line)', paddingTop: 16 }}>
          {baseRows.map((r) => <div key={r.name}>{r.name}: {r.caught}/{d.attack_cases ?? 8}</div>)}
          {ablRows.map((r) => <div key={r.name}>{r.name}: {r.caught}/{d.attack_cases ?? 8}</div>)}
          <div>Mean {(d.latency.mean_s * 1000).toFixed(2)} ms · median {(d.latency.median_s * 1000).toFixed(2)} ms · p95 {(d.latency.p95_s * 1000).toFixed(2)} ms (n={d.latency.n})</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 40, borderTop: '1px solid var(--line)', paddingTop: 24 }}>
          <section>
            <h3>Baselines vs CrossToolGuard <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· attacks caught / {d.attack_cases ?? 8}</span></h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={baseRows}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
                <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TIP} />
                <Bar dataKey="caught" fill="#5eead4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </section>
          <section>
            <h3>Ablation ladder <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· layers add detection</span></h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={ablRows}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
                <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} interval={0} angle={-14} height={64} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TIP} />
                <Bar dataKey="caught" fill="#5eead4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </section>
          <section>
            <h3>Latency <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· analyzer time in ms, n={d.latency.n}</span></h3>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={[{ x: 'mean', s: d.latency.mean_s * 1000 }, { x: 'median', s: d.latency.median_s * 1000 }, { x: 'p95', s: d.latency.p95_s * 1000 }]}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
                <XAxis dataKey="x" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TIP} />
                <Line type="monotone" dataKey="s" stroke="#5eead4" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </section>
        </div>
      )}
      <details style={{ marginTop: 24 }}>
        <summary>Development case results · {d.case_results?.length ?? 0}</summary>
        {(d.case_results ?? []).map((row) => <article key={row.id} style={{ padding: '8px 0' }}>
          <strong>{row.id}</strong> · {row.metric_group}
          <p>Expected: {row.expected_findings?.join(', ') || row.expected_integrity || row.expected_origin || 'No pattern'}{row.expected_verdict && ` · verdict ${row.expected_verdict}`}</p>
          <p>Observed: {row.patterns?.join(', ') || row.integrity || row.origin || 'No pattern'}{row.verdict && ` · verdict ${row.verdict}`}</p>
        </article>)}
      </details>
      <section style={{ marginTop: 40, borderTop: '1px solid var(--line)', paddingTop: 24 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <h2>Recorded runs</h2>
          <button onClick={() => void loadRuns()} style={{ marginLeft: 'auto', fontSize: 13 }}>Refresh runs</button>
        </div>
        <p>Each row links to its observed path. Provider `simulated` means the agent's choices were scripted. These runs are not part of the synthetic trace percentages above.</p>
        {runsError && <p role="alert">{runsError}</p>}
        {runs.map((run) => <p key={run.session_id} className="mono"><a href={`/graph?session=${encodeURIComponent(run.session_id)}`}>{run.session_id}</a> · {run.provider} · {run.policy} · {run.outcome} · {run.calls?.length ?? 0} calls · {run.model}</p>)}
        {runs.length === 0 && !runsError && <p>No recorded runs yet.</p>}
      </section>
    </div>
  );
}
