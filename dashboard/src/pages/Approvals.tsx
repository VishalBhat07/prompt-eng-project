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
    <div style={{ display: 'grid', gap: 12 }}>
      <h1 style={{ margin: 0 }}>Approval queue</h1>
      {items.map((a) => (
        <div key={a.id} className="card" style={{ padding: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <SeverityBadge level="HIGH" />
            <strong className="mono">{a.tool}</strong>
            <span className="mono" style={{ color: 'var(--muted)' }}>{a.session} · {a.id}</span>
            <RiskMeter score={a.risk} />
          </div>
          <p style={{ color: 'var(--muted)' }}>{a.explanation}</p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => decide(a.id, true)}>Approve (G)</button>
            <button onClick={() => decide(a.id, false)}>Deny (D)</button>
          </div>
        </div>
      ))}
      {items.length === 0 && <p style={{ color: 'var(--muted)' }}>Queue empty. One-shot grants: replaying a used approval re-prompts.</p>}
      <h2>Audit trail</h2>
      {log.length === 0 && <p style={{ color: 'var(--muted)' }}>No decisions yet.</p>}
      {log.map((l, i) => <div key={i} className="mono" style={{ fontSize: 14 }}>{l}</div>)}
    </div>
  );
}
