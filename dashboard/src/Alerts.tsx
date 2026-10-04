import type { Alert } from './api';
import { grantApproval } from './api';

export default function Alerts({ alerts, onGranted }: { alerts: Alert[]; onGranted: () => void }) {
  if (alerts.length === 0) return <p>No suspicious paths in this session.</p>;
  return (
    <div>
      {alerts.map((a, i) => (
        <div key={i} style={{ border: '1px solid #dc2626', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <strong>
            {a.pattern} · {a.severity} · risk {a.risk}
          </strong>
          <div>Chain: {a.tools.join(' → ')}</div>
          <div>Policy: {a.policy} · Decision: {a.verdict}</div>
          <p>{a.explanation}</p>
          {a.verdict === 'APPROVAL' && (
            <button
              onClick={async () => {
                const id = prompt('Approval ID from the blocked call response:');
                if (id && (await grantApproval(id)).granted) onGranted();
              }}
            >
              Grant approval
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
