import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

const STEPS = [
  'read_file(credentials_example.txt) → SECRET collected … ALLOW',
  'store_file(staging) → staged internally … ALLOW',
  'upload_file(sink://external) → chain SECRET → STORE → EXTERNAL … BLOCK',
];

export default function Demo() {
  const [log, setLog] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [running, setRunning] = useState(false);
  useEffect(() => {
    if (!running) return;
    setLog([]); setDone(false);
    const timers = STEPS.map((s, i) => setTimeout(() => {
      setLog((l) => [...l, s]);
      if (i === STEPS.length - 1) { setDone(true); setRunning(false); }
    }, 900 * (i + 1)));
    return () => timers.forEach(clearTimeout);
  }, [running]);
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <h1 style={{ margin: 0 }}>Demo runner</h1>
      <p style={{ color: 'var(--muted)' }}>
        Scripted cred-exfil scenario (mocked events; same shape as the live backend).
      </p>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={() => setRunning(true)} disabled={running}>
          {running ? 'Running…' : 'Run attack scenario'}
        </button>
        <button onClick={() => { setLog([]); setDone(false); }}>Reset demo</button>
      </div>
      <div className="card mono" style={{ padding: 16, minHeight: 130, fontSize: 15 }}>
        {log.length === 0 && <span style={{ color: 'var(--muted)' }}>Press run.</span>}
        {log.map((l, i) => (
          <div key={i} style={{ color: l.includes('BLOCK') ? 'var(--crit)' : 'var(--clean)' }}>{l}</div>
        ))}
      </div>
      {done && <Link to="/graph?session=S-DEMO" style={{ color: 'var(--accent)', fontWeight: 700 }}>
        Attack blocked — inspect the path in the graph explorer →</Link>}
    </div>
  );
}
