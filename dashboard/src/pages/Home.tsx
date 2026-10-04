import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import BlurText from '../components/bits/BlurText';
import CountUp from '../components/bits/CountUp';

const FEED = [
  'S-7b68 · read_file → ALLOW',
  'S-7b68 · store_file → ALLOW',
  'S-7b68 · upload_file → BLOCK · secret_exfiltration',
  'S-9f02 · search → ALLOW',
];

function LiveLine() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((v) => (v + 1) % FEED.length), 2400);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="mono" aria-live="off" style={{ fontSize: 13, color: 'var(--faint)' }}>
      <span style={{ color: 'var(--clean)' }}>● live</span>
      <span style={{ marginLeft: 12 }}>{FEED[i]}</span>
    </div>
  );
}

const STAGES: [string, string][] = [
  ['Capture', 'Every tool call and output becomes a typed event.'],
  ['Graph', 'Events link into one temporal graph per session.'],
  ['Analyze', 'Patterns, semantics, and capabilities score each path.'],
  ['Score', 'Risk 0–100 against calibrated policy bands.'],
  ['Decide', 'Ambiguous cases ask a human; attacks are blocked.'],
];

function Proof() {
  const [d, setD] = useState<{ detection_rate: number; false_positive_rate: number; latency: { p95_s: number } } | null>(null);
  useEffect(() => { fetch('/data/benchmark.json').then((r) => r.json()).then(setD).catch(() => {}); }, []);
  const stats: [string, number, string, string][] = [
    ['Detection', d ? Math.round(d.detection_rate * 100) : 0, '%', '8 of 8 targeted attacks'],
    ['False positives', d ? Math.round(d.false_positive_rate * 100) : 0, '%', '0 of 9 benign flagged'],
    ['Cross-tool-only catches', 7, '', 'invisible to single-tool checks'],
    ['Analyze p95', d ? Math.round(d.latency.p95_s * 1000) : 0, ' ms', 'of a 150 ms budget'],
  ];
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))' }}>
        {stats.map(([k, v, suffix, sub], i) => (
          <div key={k} style={{
            padding: '28px 24px', borderLeft: i === 0 ? 'none' : '1px solid var(--line)',
          }}>
            <div style={{ fontSize: 13, color: 'var(--muted)', letterSpacing: '0.04em' }}>{k}</div>
            <div className="mono" style={{ fontSize: 44, fontWeight: 700, letterSpacing: '-0.03em', margin: '4px 0' }}>
              <CountUp to={v} duration={1.4} />{suffix}
            </div>
            <div style={{ fontSize: 13.5, color: 'var(--faint)' }}>{sub}</div>
          </div>
        ))}
      </div>
      <Link to="/benchmark" style={{ fontSize: 14, color: 'var(--accent)', textDecoration: 'none' }}>Full benchmark →</Link>
    </div>
  );
}

export default function Home() {
  return (
    <div>
      <header style={{ padding: '88px 0 56px', maxWidth: 860 }}>
        <span className="eyebrow">Runtime defense for tool-using agents</span>
        <BlurText tag="h1" className="hero-blur" delay={90}
          text="Detect the attack path, not just the sentence." />
        <p className="sub" style={{ maxWidth: 620 }}>
          VeriGraph watches agent tool sessions, links actions into a graph,
          and blocks coordinated exfiltration that looks innocent one tool at a time.
        </p>
        <div style={{ display: 'flex', gap: 12, marginTop: 28 }}>
          <Link to="/graph" className="btn-primary" style={{ textDecoration: 'none', borderRadius: 8 }}>Open console</Link>
          <Link to="/demo" className="btn-ghost hairline" style={{ textDecoration: 'none', borderRadius: 8 }}>Run the demo</Link>
        </div>
        <div style={{ marginTop: 36, paddingTop: 20, borderTop: '1px solid var(--line)' }}>
          <LiveLine />
        </div>
      </header>

      <motion.section
        initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderTop: '1px solid var(--line)' }}>
        <div style={{ padding: '32px 32px 32px 0' }}>
          <div className="eyebrow" style={{ marginBottom: 12 }}>Without VeriGraph</div>
          <p className="mono" style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 2 }}>
            read_file <span style={{ color: 'var(--faint)' }}>→ ALLOW</span><br />
            store_file <span style={{ color: 'var(--faint)' }}>→ ALLOW</span><br />
            upload_file <span style={{ color: 'var(--faint)' }}>→ ALLOW</span>
          </p>
          <p style={{ marginTop: 12, color: 'var(--muted)', fontSize: 15 }}>The secret leaves. Nothing fires.</p>
        </div>
        <div style={{ padding: '32px 0 32px 32px', borderLeft: '1px solid var(--line)' }}>
          <div className="eyebrow" style={{ marginBottom: 12 }}>With VeriGraph</div>
          <p className="mono" style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 2 }}>
            read_file <span style={{ color: 'var(--faint)' }}>→ ALLOW</span><br />
            store_file <span style={{ color: 'var(--faint)' }}>→ ALLOW</span><br />
            upload_file <span style={{ color: 'var(--crit)', fontWeight: 700 }}>→ BLOCK</span>
          </p>
          <p className="mono" style={{ marginTop: 12, fontSize: 13, color: 'var(--crit)' }}>
            secret_exfiltration · CRITICAL · risk 95
          </p>
        </div>
      </motion.section>

      <section style={{ borderTop: '1px solid var(--line)', padding: '56px 0' }}>
        <div className="eyebrow" style={{ marginBottom: 20 }}>What we do</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 24 }}>
          {[
            ['Monitor', 'Every tool call and output becomes a typed event. Hashes and labels only, never raw secrets.'],
            ['Model', 'Events link into one temporal graph per session. Provenance survives summarizers and reformatting.'],
            ['Enforce', 'Patterns, semantics, and capabilities score each path. Risk maps to allow, monitor, approval, or block.'],
          ].map(([t, d]) => (
            <div key={t}>
              <div style={{ fontWeight: 650, fontSize: 16, marginBottom: 6 }}>{t}</div>
              <div style={{ fontSize: 14.5, color: 'var(--muted)', lineHeight: 1.6 }}>{d}</div>
            </div>
          ))}
        </div>
      </section>

      <section style={{ borderTop: '1px solid var(--line)', padding: '56px 0' }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>What we catch</div>
        <p className="sub" style={{ fontSize: 15, maxWidth: 640, marginBottom: 20 }}>
          Ten coordinated attack classes, each dangerous precisely because its steps look innocent alone.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 0, borderTop: '1px solid var(--line)' }}>
          {[
            ['Cross-tool exfiltration', 'Read secret, stage it, upload it.'],
            ['Distributed poisoning', 'One instruction split across three tools.'],
            ['Capability escalation', 'Read plus write plus send becomes exfil.'],
            ['Credential to network', 'Keys read, then transmitted.'],
            ['Tool rug pull', 'Approved today, malicious tomorrow.'],
            ['Context laundering', 'Malice washed through summarizers.'],
            ['Shadow workflows', 'Extra compress, upload, email nobody asked for.'],
            ['Multi-stage campaigns', 'Recon, collect, stage, exfiltrate.'],
          ].map(([t, d]) => (
            <div key={t} style={{ padding: '16px 20px 16px 0', borderBottom: '1px solid var(--line)' }}>
              <div className="mono" style={{ fontSize: 13.5 }}>{t}</div>
              <div style={{ fontSize: 13, color: 'var(--faint)', marginTop: 2 }}>{d}</div>
            </div>
          ))}
        </div>
      </section>

      <section style={{ borderTop: '1px solid var(--line)', padding: '56px 0' }}>
        <div className="eyebrow" style={{ marginBottom: 20 }}>Pipeline</div>
        <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 24 }}>
          {STAGES.map(([t, d], i) => (
            <li key={t}>
              <div className="mono" style={{ fontSize: 13, color: 'var(--accent)' }}>0{i + 1}</div>
              <div style={{ fontWeight: 600, fontSize: 15, margin: '6px 0 4px' }}>{t}</div>
              <div style={{ fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.55 }}>{d}</div>
            </li>
          ))}
        </ol>
      </section>

      <section style={{ borderTop: '1px solid var(--line)', padding: '56px 0' }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Proof, not promises</div>
        <Proof />
      </section>

      <section style={{
        borderTop: '1px solid var(--line)', padding: '64px 0', textAlign: 'center',
      }}>
        <h2>See your agents the way an attacker does.</h2>
        <p className="sub" style={{ fontSize: 16, marginTop: 8 }}>Three tool calls. Sixty seconds. One blocked exfiltration.</p>
        <div style={{ display: 'flex', gap: 12, marginTop: 24, justifyContent: 'center' }}>
          <Link to="/demo" className="btn-primary" style={{ textDecoration: 'none', borderRadius: 8 }}>Run the demo</Link>
          <Link to="/graph" className="btn-ghost hairline" style={{ textDecoration: 'none', borderRadius: 8 }}>Open console</Link>
        </div>
      </section>

      <section style={{ borderTop: '1px solid var(--line)', padding: '56px 0' }}>
        <div className="eyebrow" style={{ marginBottom: 20 }}>Architecture</div>
        <svg viewBox="0 0 920 120" role="img" aria-label="VeriGraph layered architecture" style={{ width: '100%' }}>
          {['Agent', 'Proxy', 'Graph', 'Analyze', 'Policy'].map((l, i) => (
            <g key={l}>
              <text x={30 + i * 180} y={30} fill="#63636b" fontSize={12} fontFamily="monospace">0{i + 1}</text>
              <text x={30 + i * 180} y={58} fill="#fafafa" fontSize={19} fontWeight={600}>{l}</text>
              <text x={30 + i * 180} y={82} fill="#63636b" fontSize={12.5}>
                {['plans + acts', 'events, gated', 'one graph/session', 'paths scored', 'allow → block'][i]}
              </text>
              {i < 4 && <text x={172 + i * 180} y={58} fill="#33333a" fontSize={18}>→</text>}
            </g>
          ))}
        </svg>
        <p className="mono" style={{ fontSize: 12.5, color: 'var(--faint)', marginTop: 8 }}>
          events carry hashes + labels, never raw secrets · verdicts gate the last hop
        </p>
      </section>

      <footer style={{ borderTop: '1px solid var(--line)', padding: '28px 0 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13.5, color: 'var(--faint)' }}>
          <span>VeriGraph - graph-based runtime defense for tool-using agents</span>
          <span className="mono">repo · docs · course project</span>
        </div>
      </footer>
    </div>
  );
}
