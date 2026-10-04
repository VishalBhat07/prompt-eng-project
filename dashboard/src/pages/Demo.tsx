import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import DepthText from '../components/bits/DepthText';

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
    <div>
      <header style={{ padding: '56px 0 28px', maxWidth: 720 }}>
        <span className="eyebrow">Classroom demo</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Demo runner</h1>
        <p className="sub" style={{ fontSize: 16 }}>One click. Three tool calls. Watch the third one die.</p>
      </header>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn-primary" style={{ borderRadius: 8 }} onClick={() => setRunning(true)} disabled={running}>
          {running ? 'Running…' : 'Run attack scenario'}
        </button>
        <button onClick={() => { setLog([]); setDone(false); }}>Reset</button>
      </div>
      <div className="mono" style={{
        marginTop: 20, border: '1px solid var(--line)', borderRadius: 12,
        padding: 20, minHeight: 140, fontSize: 14.5, lineHeight: 2,
      }}>
        {log.length === 0 && <span style={{ color: 'var(--faint)' }}>Press run.</span>}
        {log.map((l, i) => (
          <div key={i} style={{ color: l.includes('BLOCK') ? 'var(--crit)' : 'var(--muted)' }}>{l}</div>
        ))}
      </div>
      {done && (
        <div style={{ marginTop: 24 }}>
          <DepthText text="Attack blocked." layers={5} depth={0.6} fontSize="clamp(30px,4vw,46px)"
            fontWeight={700} faceColor="#fafafa" depthColor="#134e4a" tilt={8} shadow={false} />
          <Link to="/graph?session=S-DEMO" style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'none' }}>
            Inspect the path in the graph explorer →
          </Link>
        </div>
      )}
    </div>
  );
}
