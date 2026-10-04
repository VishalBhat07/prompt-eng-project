import { useState } from 'react';
import { RiskMeter, SeverityBadge } from '../components/Severity';
import type { Approval } from '../data/types';

const PENDING: Approval[] = [
  {
    id: 'a91f', session: 'S-DEMO', tool: 'upload_file', risk: 0.72,
    explanation: 'Low-trust instruction steers a privileged upload. Grant once to allow, deny to keep blocked.',
  },
];

export default function Approvals() {
  const [items, setItems] = useState(PENDING);
  const [log, setLog] = useState<string[]>([]);
  const decide = (id: string, ok: boolean) => {
    setItems((p) => p.filter((a) => a.id !== id));
    setLog((l) => [`${ok ? 'Granted' : 'Denied'} ${id} — ${new Date().toLocaleTimeString()}`, ...l]);
  };
  return (
    <div>
      <header style={{ padding: '56px 0 28px', maxWidth: 720 }}>
        <span className="eyebrow">Human in the loop</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Approvals</h1>
        <p className="sub" style={{ fontSize: 16 }}>Ambiguous cases wait here. Grants are one-shot by design.</p>
      </header>
      <div style={{ borderTop: '1px solid var(--line)' }}>
        {items.map((a) => (
          <div key={a.id} style={{ padding: '24px 0', borderBottom: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <SeverityBadge level="HIGH" />
              <strong className="mono" style={{ fontSize: 15 }}>{a.tool}</strong>
              <span className="mono" style={{ fontSize: 13, color: 'var(--faint)' }}>{a.session} · {a.id}</span>
              <RiskMeter score={a.risk} />
            </div>
            <p style={{ color: 'var(--muted)', fontSize: 15, marginTop: 8 }}>{a.explanation}</p>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button onClick={() => decide(a.id, true)}>Approve</button>
              <button onClick={() => decide(a.id, false)}>Deny</button>
            </div>
          </div>
        ))}
        {items.length === 0 && <p style={{ color: 'var(--faint)', padding: '24px 0' }}>Queue empty.</p>}
      </div>
      <h2 style={{ marginTop: 40 }}>Audit trail</h2>
      {log.length === 0 && <p style={{ color: 'var(--faint)', fontSize: 14.5 }}>No decisions yet.</p>}
      {log.map((l, i) => <div key={i} className="mono" style={{ fontSize: 13.5, color: 'var(--muted)', padding: '4px 0' }}>{l}</div>)}
    </div>
  );
}
