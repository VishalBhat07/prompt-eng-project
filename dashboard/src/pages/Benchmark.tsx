import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { BenchDoc } from '../data/types';

const TIP = { background: 'var(--bg-1)', border: '1px solid var(--line)', fontSize: 13, color: 'var(--ink)' };
// SVG attributes (ticks, grid) can't use var(); fixed mid-gray reads on both themes.
const AXIS = { fill: '#888888', fontSize: 12 };
const GRID = 'rgba(128,128,128,0.25)';

export default function Benchmark() {
  const [d, setD] = useState<BenchDoc | null>(null);
  const [runs, setRuns] = useState<{ session_id: string; outcome: string; policy: string; provider: string; model: string; calls: { tool: string; verdict?: string }[] }[]>([]);
  const [table, setTable] = useState(false);
  const [runsError, setRunsError] = useState('');
  const loadRuns = () => fetch('/api/runs').then((r) => r.json())
    .then((body) => { setRuns(body.runs ?? []); setRunsError(''); })
    .catch(() => setRunsError('Could not load recorded runs from the gateway.'));
  useEffect(() => { fetch('/data/benchmark.json').then((r) => r.json()).then(setD).catch(() => {}); }, []);
  useEffect(() => { void loadRuns(); }, []);
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
      <div style={{ display: 'flex', gap: 12, padding: '12px 0', borderTop: '1px solid var(--line)' }}>
        <button style={{ fontSize: 13 }} onClick={() => setTable((t) => !t)}>{table ? 'View as charts' : 'View as table'}</button>
        <a href="/data/benchmark.json" download style={{ fontSize: 13.5, color: 'var(--accent)', textDecoration: 'none' }}>Download JSON</a>
      </div>
      {table ? (
        <div className="mono" style={{ fontSize: 13.5, color: 'var(--muted)', lineHeight: 2, borderTop: '1px solid var(--line)', paddingTop: 16 }}>
          {baseRows.map((r) => <div key={r.name}>{r.name}: {r.caught}/{d.attack_cases ?? 8}</div>)}
          {ablRows.map((r) => <div key={r.name}>{r.name}: {r.caught}/{d.attack_cases ?? 8}</div>)}
          <div>latency mean {d.latency.mean_s}s · p95 {d.latency.p95_s}s (n={d.latency.n})</div>
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
            <h3>Latency <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· analyze() seconds, n={d.latency.n}</span></h3>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={[{ x: 'mean', s: d.latency.mean_s }, { x: 'p95', s: d.latency.p95_s }]}>
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
