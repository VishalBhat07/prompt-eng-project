import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RiskMeter, SeverityBadge } from '../components/Severity';
import { listSessions, type SessionSummary } from '../data/provider';

export default function Sessions() {
  const [rows, setRows] = useState<SessionSummary[]>([]);
  useEffect(() => { listSessions().then(setRows).catch(() => {}); }, []);
  const kpis: [string, string][] = [
    ['Active sessions', String(rows.length)],
    ['Findings today', String(rows.reduce((a, r) => a + r.findings, 0))],
    ['Blocked actions', String(rows.reduce((a, r) => a + r.blocked, 0))],
    ['Avg max-risk', rows.length ? String(Math.round((rows.reduce((a, r) => a + r.maxRisk, 0) / rows.length) * 100)) : '…'],
  ];
  return (
    <div style={{ display: 'grid', gap: 20 }}>
      <h1 style={{ margin: 0 }}>Sessions</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 12 }}>
        {kpis.map(([k, v]) => (
          <div key={k} className="card" style={{ padding: 18 }}>
            <div style={{ color: 'var(--muted)', fontSize: 14 }}>{k}</div>
            <div className="mono" style={{ fontSize: 36, color: 'var(--accent)' }}>{v}</div>
          </div>
        ))}
      </div>
      <div className="card" style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 15 }}>
          <thead>
            <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
              <th style={{ padding: 12 }}>Session</th><th>Status</th><th>Tools</th>
              <th>Events</th><th>Findings</th><th>Max risk</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                <td style={{ padding: 12 }}>
                  <Link to={`/graph?session=${r.id}`} className="mono" style={{ color: 'var(--accent)' }}>{r.id}</Link>
                </td>
                <td><SeverityBadge level={r.status} /></td>
                <td className="mono">{r.tools}</td>
                <td className="mono">{r.events}</td>
                <td className="mono">{r.findings}</td>
                <td><RiskMeter score={r.maxRisk} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
