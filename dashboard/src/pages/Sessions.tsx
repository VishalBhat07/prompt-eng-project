import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RiskMeter, SeverityBadge } from '../components/Severity';
import CountUp from '../components/bits/CountUp';
import { listSessions, type SessionSummary } from '../data/provider';

export default function Sessions() {
  const [rows, setRows] = useState<SessionSummary[]>([]);
  useEffect(() => { listSessions().then(setRows).catch(() => {}); }, []);
  const kpis: [string, number, string][] = [
    ['Active sessions', rows.length, ''],
    ['Findings', rows.reduce((a, r) => a + r.findings, 0), ''],
    ['Blocked', rows.reduce((a, r) => a + r.blocked, 0), ''],
    ['Avg max-risk', rows.length ? Math.round((rows.reduce((a, r) => a + r.maxRisk, 0) / rows.length) * 100) : 0, ''],
  ];
  return (
    <div>
      <header style={{ padding: '56px 0 32px', maxWidth: 720 }}>
        <span className="eyebrow">Monitor</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Sessions</h1>
        <p className="sub" style={{ fontSize: 16 }}>Every agent run, one graph. Suspicious chains surface here first.</p>
      </header>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', borderTop: '1px solid var(--line)' }}>
        {kpis.map(([k, v, suffix], i) => (
          <div key={k} style={{ padding: '20px 20px 20px 0', borderLeft: i === 0 ? 'none' : '1px solid var(--line)', paddingLeft: i === 0 ? 0 : 20 }}>
            <div style={{ fontSize: 13, color: 'var(--muted)' }}>{k}</div>
            <div className="mono" style={{ fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em' }}>
              <CountUp to={v} duration={1} />{suffix}
            </div>
          </div>
        ))}
      </div>
      <div style={{ borderTop: '1px solid var(--line)', marginTop: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: 'var(--faint)', textAlign: 'left', fontSize: 12.5, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              <th style={{ padding: '14px 16px 14px 0', fontWeight: 600 }}>Session</th>
              <th style={{ fontWeight: 600 }}>Status</th><th style={{ fontWeight: 600 }}>Tools</th>
              <th style={{ fontWeight: 600 }}>Events</th><th style={{ fontWeight: 600 }}>Findings</th><th style={{ fontWeight: 600 }}>Max risk</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} style={{ borderTop: '1px solid var(--line)' }}>
                <td style={{ padding: '14px 16px 14px 0' }}>
                  <Link to={`/graph?session=${r.id}`} className="mono"
                    style={{ color: 'var(--ink)', textDecoration: 'none', fontSize: 14.5 }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--ink)')}>
                    {r.id}
                  </Link>
                </td>
                <td><SeverityBadge level={r.status} /></td>
                <td className="mono" style={{ color: 'var(--muted)' }}>{r.tools}</td>
                <td className="mono" style={{ color: 'var(--muted)' }}>{r.events}</td>
                <td className="mono" style={{ color: r.findings ? 'var(--crit)' : 'var(--muted)' }}>{r.findings}</td>
                <td><RiskMeter score={r.maxRisk} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
