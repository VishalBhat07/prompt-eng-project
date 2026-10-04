import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { BenchDoc } from '../data/types';

export default function Benchmark() {
  const [d, setD] = useState<BenchDoc | null>(null);
  const [table, setTable] = useState(false);
  useEffect(() => { fetch('/data/benchmark.json').then((r) => r.json()).then(setD).catch(() => {}); }, []);
  if (!d) return <p style={{ color: 'var(--muted)' }}>Loading benchmark.json…</p>;
  const baseRows = Object.entries(d.baselines).map(([k, v]) => ({ name: k, caught: v.caught }));
  const ablRows = Object.entries(d.ablation).map(([k, v]) => ({ name: k.replace('-', ' +'), caught: v.caught }));
  return (
    <div style={{ display: 'grid', gap: 20 }}>
      <h1 style={{ margin: 0 }}>Benchmark <span className="mono" style={{ fontSize: 14, color: 'var(--muted)' }}>
        n={d.cases} · detection {Math.round(d.detection_rate * 100)}% · FPR {Math.round(d.false_positive_rate * 100)}%</span></h1>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={() => setTable((t) => !t)}>{table ? 'View as charts' : 'View as table'}</button>
        <a href="/data/benchmark.json" download style={{ color: 'var(--accent)' }}>Download JSON</a>
      </div>
      {table ? (
        <div className="card" style={{ padding: 16 }}>
          {baseRows.map((r) => <div key={r.name} className="mono" style={{ fontSize: 14 }}>{r.name}: {r.caught}/8</div>)}
          {ablRows.map((r) => <div key={r.name} className="mono" style={{ fontSize: 14 }}>{r.name}: {r.caught}/8</div>)}
          <div className="mono" style={{ fontSize: 14 }}>latency mean {d.latency.mean_s}s · p95 {d.latency.p95_s}s (n={d.latency.n})</div>
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: 16 }}>
            <h3>Baselines vs VeriGraph (attacks caught / 8)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={baseRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="name" tick={{ fill: '#9aa4b2', fontSize: 12 }} />
                <YAxis tick={{ fill: '#9aa4b2' }} />
                <Tooltip contentStyle={{ background: '#11151c', border: '1px solid rgba(255,255,255,0.15)' }} />
                <Bar dataKey="caught" fill="#2dd4bf" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="card" style={{ padding: 16 }}>
            <h3>Ablation ladder (layers add detection)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={ablRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="name" tick={{ fill: '#9aa4b2', fontSize: 12 }} interval={0} angle={-12} height={60} />
                <YAxis tick={{ fill: '#9aa4b2' }} />
                <Tooltip contentStyle={{ background: '#11151c', border: '1px solid rgba(255,255,255,0.15)' }} />
                <Bar dataKey="caught" fill="#2dd4bf" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="card" style={{ padding: 16 }}>
            <h3>Latency — analyze() seconds (n={d.latency.n})</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={[{ x: 'mean', s: d.latency.mean_s }, { x: 'p95', s: d.latency.p95_s }]}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="x" tick={{ fill: '#9aa4b2' }} />
                <YAxis tick={{ fill: '#9aa4b2' }} />
                <Tooltip contentStyle={{ background: '#11151c', border: '1px solid rgba(255,255,255,0.15)' }} />
                <Legend />
                <Line type="monotone" dataKey="s" stroke="#2dd4bf" name="seconds" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
