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
    <div style={{ display: 'grid', gap: 12 }}>
      <h1 style={{ margin: 0 }}>Findings</h1>
      <div style={{ display: 'flex', gap: 8 }}>
        {['ALL', 'CRITICAL', 'HIGH'].map((s) => (
          <button key={s} onClick={() => setSev(s)}
            style={{ borderColor: sev === s ? 'var(--accent)' : undefined }}>{s}</button>
        ))}
      </div>
      {rows.map((p) => (
        <div key={p.pattern} className="card" style={{ padding: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <SeverityBadge level={p.severity as 'CRITICAL' | 'HIGH'} pulse />
            <strong className="mono">{p.pattern}</strong>
            <RiskMeter score={p.risk} />
            <span className="mono" style={{ color: 'var(--muted)' }}>{p.tools.join(' → ')}</span>
          </div>
          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
            <button onClick={() => setOpen(open === p.pattern ? null : p.pattern)}>
              {open === p.pattern ? 'Hide evidence' : 'Evidence'}
            </button>
            <Link to={`/graph?session=S-DEMO`}>Show in graph</Link>
          </div>
          {open === p.pattern && <p style={{ color: 'var(--muted)' }}>{p.explanation}</p>}
        </div>
      ))}
      {rows.length === 0 && <p style={{ color: 'var(--muted)' }}>No findings at this severity.</p>}
    </div>
  );
}
