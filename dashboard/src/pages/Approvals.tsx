import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

interface Pending { id: string; session: string; server: string; tool: string; expires_at: number; argument_fields?: string[]; arguments_sha256?: string; data_class?: string }

export default function Approvals() {
  const [items, setItems] = useState<Pending[]>([]);
  const [message, setMessage] = useState('');
  const refresh = async () => {
    try {
      const response = await fetch('/api/approvals');
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status})`);
      setItems(body.pending); setMessage('');
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Request failed'); }
  };
  const decide = async (id: string, grant: boolean) => {
    try {
      const response = await fetch(grant ? '/api/approvals/grant' : `/api/approvals/${encodeURIComponent(id)}/deny`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: grant ? JSON.stringify({ approval_id: id }) : '{}',
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? `Decision failed (${response.status})`);
      await refresh();
      setMessage(`${grant ? 'Granted' : 'Denied'} ${id}. A grant is consumed only if the matching call is retried before expiry.`);
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Decision failed'); }
  };
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 4000);
    return () => window.clearInterval(timer);
  }, []);
  return <div>
    <header style={{ padding: '56px 0 28px', maxWidth: 720 }}><span className="eyebrow">Human review</span>
      <h1>Approvals</h1><p className="sub">Pending sensitive calls from the running gateway. Grants expire and can be used once.</p></header>
    <button onClick={refresh}>Refresh queue</button>
    {message && <p role="status">{message}</p>}
    <div style={{ marginTop: 24, borderTop: '1px solid var(--line)' }}>
      {items.map((item) => <article key={item.id} style={{ padding: '20px 0', borderBottom: '1px solid var(--line)' }}>
        <strong className="mono">{item.server}/{item.tool}</strong> · <Link to={`/graph?session=${encodeURIComponent(item.session)}`}>{item.session}</Link>
        <p>Argument fields: {item.argument_fields?.join(', ') || 'none'} · Data class: {item.data_class ?? 'unknown'}</p>
        {item.arguments_sha256 && <p className="mono">Argument hash: {item.arguments_sha256.slice(0, 16)}</p>}
        <p>Expires {new Date(item.expires_at * 1000).toLocaleTimeString()}</p>
        <button onClick={() => decide(item.id, true)}>Grant once</button>
        <button onClick={() => decide(item.id, false)} style={{ marginLeft: 8 }}>Deny</button>
      </article>)}
      {items.length === 0 && <p>No pending approvals loaded.</p>}
    </div>
  </div>;
}
