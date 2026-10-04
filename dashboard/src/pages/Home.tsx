import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { RiskMeter, SeverityBadge } from '../components/Severity';

const TICKER = [
  { t: 'session started', s: 'S-7b68fe6a', k: 'CLEAN' },
  { t: 'edge added', s: 'read_file → store_file', k: 'CLEAN' },
  { t: 'finding raised', s: 'secret_exfiltration · CRITICAL', k: 'CRITICAL' },
  { t: 'action blocked', s: 'upload_file → external', k: 'CRITICAL' },
  { t: 'approval granted', s: 'untrusted-to-privileged', k: 'HIGH' },
] as const;

function Ticker() {
  const [items, setItems] = useState<typeof TICKER[number][]>([...TICKER]);
  useEffect(() => {
    const id = setInterval(() => setItems((p) => [...p.slice(1), p[0]]), 2200);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="card mono" aria-label="live event ticker"
      style={{ padding: 12, fontSize: 14, height: 132, overflow: 'hidden' }}>
      {items.slice(0, 4).map((e, i) => (
        <div key={i} style={{ opacity: 1 - i * 0.22, padding: '3px 0', color: 'var(--muted)' }}>
          <span style={{ color: e.k === 'CRITICAL' ? 'var(--crit)' : e.k === 'HIGH' ? 'var(--high)' : 'var(--clean)' }}>●</span>
          {' '}{e.t} <span style={{ color: 'var(--ink)' }}>{e.s}</span>
        </div>
      ))}
    </div>
  );
}

const STAGES = [
  ['Capture', 'Proxy records every tool call and output as events.'],
  ['Graph', 'Events become a temporal attack graph per session.'],
  ['Analyze', 'Patterns, semantics, and capabilities score each path.'],
  ['Score', 'Risk 0–100 with calibrated policy bands.'],
  ['Approve / Block', 'Humans approve the ambiguous; attacks are blocked.'],
];

function Proof() {
  const [d, setD] = useState<{ detection_rate: number; false_positive_rate: number; latency: { p95_s: number } } | null>(null);
  useEffect(() => { fetch('/data/benchmark.json').then((r) => r.json()).then(setD).catch(() => {}); }, []);
  const cards = [
    ['Detection rate', d ? `${Math.round(d.detection_rate * 100)}%` : '…', '8/8 targeted attacks'],
    ['False positives', d ? `${Math.round(d.false_positive_rate * 100)}%` : '…', '0 of 9 benign flagged'],
    ['Cross-tool-only catches', '7', 'invisible to single-tool checks'],
    ['Analyze p95', d ? `${Math.round(d.latency.p95_s * 1000)} ms` : '…', 'well inside 150 ms budget'],
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
      {cards.map(([k, v, sub]) => (
        <div key={k} className="card" style={{ padding: 20 }}>
          <div style={{ color: 'var(--muted)', fontSize: 14 }}>{k}</div>
          <div className="mono" style={{ fontSize: 40, color: 'var(--accent)' }}>{v}</div>
          <div style={{ color: 'var(--muted)', fontSize: 14 }}>{sub}</div>
        </div>
      ))}
      <Link to="/benchmark" style={{ color: 'var(--accent)' }}>Full benchmark →</Link>
    </div>
  );
}

export default function Home() {
  return (
    <div style={{ display: 'grid', gap: 48 }}>
      <section style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24, alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 52, lineHeight: 1.05, margin: '0 0 12px' }}>
            Detect the attack path,<br />not just the sentence.
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: 20, maxWidth: 560 }}>
            VeriGraph watches agent tool sessions, builds the action/data-flow graph,
            and blocks coordinated exfiltration that looks innocent one tool at a time.
          </p>
          <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
            <Link to="/graph" className="card"
              style={{ padding: '12px 24px', textDecoration: 'none', color: 'var(--ink)', background: 'var(--accent)', border: 'none', fontWeight: 700 }}>
              Open console
            </Link>
            <Link to="/demo" className="card"
              style={{ padding: '12px 24px', textDecoration: 'none', color: 'var(--ink)' }}>
              Run the demo
            </Link>
          </div>
        </div>
        <Ticker />
      </section>

      <motion.section initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="card" style={{ padding: 20 }}>
          <h3>Without VeriGraph</h3>
          <p className="mono" style={{ color: 'var(--muted)' }}>read_file → ALLOW<br />store_file → ALLOW<br />upload_file → ALLOW</p>
          <p style={{ color: 'var(--crit)' }}>Secret leaves. Nothing fires.</p>
        </div>
        <motion.div className="card glow-crit" initial={{ x: 30, opacity: 0.4 }} whileInView={{ x: 0, opacity: 1 }}
          viewport={{ once: true }} style={{ padding: 20 }}>
          <h3>With VeriGraph</h3>
          <p className="mono" style={{ color: 'var(--muted)' }}>read_file → ALLOW<br />store_file → ALLOW<br />upload_file → <b style={{ color: 'var(--crit)' }}>BLOCK</b></p>
          <p><SeverityBadge level="CRITICAL" /> secret_exfiltration · risk <RiskMeter score={0.95} /></p>
        </motion.div>
      </motion.section>

      <section>
        <h2>Pipeline</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12 }}>
          {STAGES.map(([t, d], i) => (
            <div key={t} className="card" style={{ padding: 16 }}>
              <div className="mono" style={{ color: 'var(--accent)' }}>{i + 1}</div>
              <strong>{t}</strong>
              <p style={{ color: 'var(--muted)', fontSize: 14 }}>{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>Proof, not promises</h2>
        <Proof />
      </section>

      <section>
        <h2>Architecture</h2>
        <svg viewBox="0 0 900 190" role="img" aria-label="VeriGraph layered architecture"
          className="card" style={{ width: '100%', padding: 12 }}>
          {['Agent', 'Proxy', 'Graph', 'Analyze', 'Policy'].map((l, i) => (
            <g key={l}>
              <rect x={20 + i * 175} y={55} width={150} height={70} rx={8}
                fill={i === 4 ? 'rgba(45,212,191,0.12)' : '#171c26'}
                stroke={i === 4 ? '#2dd4bf' : 'rgba(255,255,255,0.15)'} />
              <text x={95 + i * 175} y={95} textAnchor="middle" fill="#edf1f7" fontSize={16}>{l}</text>
              {i < 4 && <text x={178 + i * 175} y={95} textAnchor="middle" fill="#9aa4b2" fontSize={20}>→</text>}
            </g>
          ))}
          <text x={20} y={160} fill="#9aa4b2" fontSize={13}>events (hashes + labels, never raw secrets) flow left → right; verdicts gate the last hop</text>
        </svg>
      </section>

      <footer style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16, color: 'var(--muted)', fontSize: 14 }}>
        VeriGraph — graph-based runtime defense for tool-using agents · <span className="mono">repo · docs · course project</span>
      </footer>
    </div>
  );
}
