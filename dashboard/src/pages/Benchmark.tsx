import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { BenchDoc } from '../data/types';

const TIP = { background: '#0e0e13', border: '1px solid rgba(255,255,255,0.12)', fontSize: 13 };
const AXIS = { fill: '#63636b', fontSize: 12 };

export default function Benchmark() {
  const [d, setD] = useState<BenchDoc | null>(null);
  const [table, setTable] = useState(false);
  useEffect(() => { fetch('/data/benchmark.json').then((r) => r.json()).then(setD).catch(() => {}); }, []);
  if (!d) return <p style={{ color: 'var(--faint)' }}>Loading benchmark.json…</p>;
  const baseRows = Object.entries(d.baselines).map(([k, v]) => ({ name: k, caught: v.caught }));
  const ablRows = Object.entries(d.ablation).map(([k, v]) => ({ name: k.replace('-', ' +'), caught: v.caught }));
  return (
    <div>
      <header style={{ padding: '56px 0 28px', maxWidth: 720 }}>
        <span className="eyebrow">Evidence</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Benchmark</h1>
        <p className="sub" style={{ fontSize: 16 }}>
          19 cases · detection {Math.round(d.detection_rate * 100)}% · FPR {Math.round(d.false_positive_rate * 100)}%
        </p>
      </header>
      <div style={{ display: 'flex', gap: 12, padding: '12px 0', borderTop: '1px solid var(--line)' }}>
        <button style={{ fontSize: 13 }} onClick={() => setTable((t) => !t)}>{table ? 'View as charts' : 'View as table'}</button>
        <a href="/data/benchmark.json" download style={{ fontSize: 13.5, color: 'var(--accent)', textDecoration: 'none' }}>Download JSON</a>
      </div>
      {table ? (
        <div className="mono" style={{ fontSize: 13.5, color: 'var(--muted)', lineHeight: 2, borderTop: '1px solid var(--line)', paddingTop: 16 }}>
          {baseRows.map((r) => <div key={r.name}>{r.name}: {r.caught}/8</div>)}
          {ablRows.map((r) => <div key={r.name}>{r.name}: {r.caught}/8</div>)}
          <div>latency mean {d.latency.mean_s}s · p95 {d.latency.p95_s}s (n={d.latency.n})</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 40, borderTop: '1px solid var(--line)', paddingTop: 24 }}>
          <section>
            <h3>Baselines vs VeriGraph <span style={{ color: 'var(--faint)', fontWeight: 400 }}>· attacks caught / 8</span></h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={baseRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" vertical={false} />
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
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" vertical={false} />
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
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" vertical={false} />
                <XAxis dataKey="x" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TIP} />
                <Line type="monotone" dataKey="s" stroke="#5eead4" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </section>
        </div>
      )}
    </div>
  );
}
