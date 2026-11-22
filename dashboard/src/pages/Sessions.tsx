import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RiskMeter, SeverityBadge } from '../components/Severity';
import CountUp from '../components/bits/CountUp';
import { listSessions, type SessionSummary } from '../data/provider';

export default function Sessions() {
  const [rows, setRows] = useState<SessionSummary[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [clearing, setClearing] = useState(false);
  useEffect(() => {
    let active = true;
    const refresh = () => listSessions().then((next) => { if (active) { setRows(next); setError(''); } })
      .catch((e: Error) => { if (active) setError(e.message); });
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const clearSessions = async () => {
    if (!window.confirm('Delete saved run snapshots and clear live gateway sessions? Approved tool inventories are kept.')) return;
    setClearing(true); setError(''); setNotice('');
    try {
      const response = await fetch('/api/sessions', { method: 'DELETE' });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? `Clear failed (${response.status})`);
      setRows([]);
      setNotice(`Cleared ${body.cleared_saved_runs ?? 0} saved run snapshot(s) and live sessions. Inventories are unchanged.`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Clear failed'); }
    finally { setClearing(false); }
  };
  const kpis: [string, number, string][] = [
    ['Recorded sessions', rows.length, ''],
    ['Suspicious signals', rows.reduce((a, r) => a + (r.signals ?? 0), 0), ''],
    ['Blocked', rows.reduce((a, r) => a + r.blocked, 0), ''],
    ['Attack paths', rows.reduce((a, r) => a + r.findings, 0), ''],
  ];
  return (
    <div>
      <header style={{ padding: '56px 0 32px', maxWidth: 720 }}>
        <span className="eyebrow">Monitor</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Sessions</h1>
        <p className="sub" style={{ fontSize: 16 }}>Every agent run, one graph. Suspicious chains surface here first.</p>
      </header>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
        <button onClick={() => void clearSessions()} disabled={clearing || rows.length === 0}>
          {clearing ? 'Clearing…' : 'Clear saved runs'}
        </button>
        <span style={{ color: 'var(--faint)', fontSize: 12 }}>Removes run snapshots under data/runs and live session state. Approved inventories are kept.</span>
      </div>
      <p>A completed run can contain suspicious output without an attack path. Severity describes observed evidence; run state describes execution. Path risk is shown only when an attack path was detected. Possible paths are hypotheses.</p>
      {!error && rows.length === 0 && <p>No live sessions yet. Run a task through the gateway, then refresh this page.</p>}
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
      <div role="region" aria-label="Recorded sessions table" tabIndex={0} style={{ borderTop: '1px solid var(--line)', marginTop: 8, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: 'var(--faint)', textAlign: 'left', fontSize: 12.5, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              <th style={{ padding: '14px 16px 14px 0', fontWeight: 600 }}>Session</th>
              <th>Severity</th><th>Run state</th><th>Tools</th><th>Events</th><th>Signals</th><th>Attack paths</th><th>Possible paths</th><th>Path risk</th>
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
                  <div><Link to={`/demo?session=${encodeURIComponent(r.id)}`} style={{ fontSize: 12 }}>Open run / approvals</Link></div>
                </td>
                <td><SeverityBadge level={r.status} /></td>
                <td className="mono">{r.outcome ?? r.run_status ?? 'recorded'}</td>
                <td className="mono" style={{ color: 'var(--muted)' }}>{r.tools}</td>
                <td className="mono" style={{ color: 'var(--muted)' }}>{r.events}</td>
                <td className="mono">{r.signals ?? 0}</td>
                <td className="mono" style={{ color: r.findings ? 'var(--crit)' : 'var(--muted)' }}>{r.findings}</td>
                <td className="mono">{r.possible_paths ?? 0}</td>
                <td>{r.findings ? <RiskMeter score={r.maxRisk} /> : <span title="No detected attack path to score">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
