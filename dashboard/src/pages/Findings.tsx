import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RiskMeter, SeverityBadge } from '../components/Severity';
import { loadSession, type AttackPath } from '../data/provider';

export default function Findings() {
  const [paths, setPaths] = useState<AttackPath[]>([]);
  const [sev, setSev] = useState('ALL');
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { loadSession('S-DEMO').then((d) => setPaths(d.paths)).catch(() => {}); }, []);
  const rows = paths.filter((p) => sev === 'ALL' || p.severity === sev);
  return (
    <div>
      <header style={{ padding: '56px 0 28px', maxWidth: 720 }}>
        <span className="eyebrow">Review</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Findings</h1>
        <p className="sub" style={{ fontSize: 16 }}>Every suspicious path, with its evidence. Hover evidence to focus.</p>
      </header>
      <div style={{ display: 'flex', gap: 8, padding: '12px 0', borderTop: '1px solid var(--line)' }}>
        {['ALL', 'CRITICAL', 'HIGH'].map((s) => (
          <button key={s} onClick={() => setSev(s)}
            style={{ borderColor: sev === s ? 'var(--accent)' : undefined, fontSize: 13 }}>{s}</button>
        ))}
      </div>
      <div style={{ display: 'grid', gap: 0, borderTop: '1px solid var(--line)' }}>
        {rows.map((p) => (
          <article key={p.pattern} style={{ padding: '24px 0', borderBottom: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <SeverityBadge level={p.severity as 'CRITICAL' | 'HIGH'} pulse />
              <strong className="mono" style={{ fontSize: 15 }}>{p.pattern}</strong>
              <RiskMeter score={p.risk} />
            </div>
            <div className="mono" style={{ fontSize: 13.5, color: 'var(--muted)', marginTop: 8 }}>
              {p.tools.join(' → ')}
            </div>
            <div style={{ marginTop: 10, display: 'flex', gap: 12 }}>
              <button style={{ fontSize: 13 }} onClick={() => setOpen(open === p.pattern ? null : p.pattern)}>
                {open === p.pattern ? 'Hide evidence' : 'Evidence'}
              </button>
              <Link to="/graph?session=S-DEMO" style={{ fontSize: 13.5, color: 'var(--accent)', textDecoration: 'none' }}>
                Show in graph →
              </Link>
            </div>
            {open === p.pattern && (
              <p style={{ marginTop: 12, maxWidth: 720, color: 'var(--muted)', fontSize: 15, lineHeight: 1.65 }}>
                {p.explanation}
              </p>
            )}
          </article>
        ))}
        {rows.length === 0 && <p style={{ color: 'var(--faint)', padding: '24px 0' }}>No findings at this severity.</p>}
      </div>
    </div>
  );
}
