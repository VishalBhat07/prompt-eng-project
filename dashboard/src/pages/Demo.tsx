import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

interface Step { server: string; tool: string; arguments: Record<string, unknown>; verdict: string; observation: string; approval_id?: string }
interface Tool { server: string; tool: string; description: string }

const VERDICT_COLOR: Record<string, string> = {
  ALLOW: 'var(--clean)', MONITOR: 'var(--muted)', APPROVAL: 'var(--high)',
  BLOCK: 'var(--crit)', ERROR: 'var(--crit)',
};

export default function Demo() {
  const [task, setTask] = useState('Summarize the invoice and calculate its total with tax');
  const [tools, setTools] = useState<Tool[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [session, setSession] = useState('');
  const [running, setRunning] = useState(false);
  const [outcome, setOutcome] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/api/tools/list').then((r) => r.json()).then((d) => setTools(d.tools ?? []))
      .catch(() => setError('Proxy offline. Start it: MODE=enforcing uvicorn crosstoolguard.gateway.proxy:app --port 8000'));
  }, []);

  const run = async () => {
    setRunning(true); setSteps([]); setOutcome(''); setError('');
    let res;
    try {
      const r = await fetch('/api/agent/run', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });
      res = await r.json();
    } catch {
      setError('Run failed: proxy unreachable.'); setRunning(false); return;
    }
    setSession(res.session_id);
    for (const s of res.steps) {
      await new Promise((r) => setTimeout(r, 650));
      setSteps((p) => [...p, s]);
    }
    setOutcome(res.done ? 'Task complete.' : res.steps?.at(-1)?.verdict === 'BLOCK'
      ? 'Halted: policy blocked a step.'
      : res.steps?.at(-1)?.verdict === 'APPROVAL'
        ? 'Halted: a step needs approval (see Approvals).'
        : 'Halted.');
    setRunning(false);
  };

  return (
    <div>
      <header style={{ padding: '56px 0 28px', maxWidth: 720 }}>
        <span className="eyebrow">Sandbox</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Playground</h1>
        <p className="sub" style={{ fontSize: 16 }}>
          Type a task. The agent plans with the server model, every call is enforced live,
          and the trace below is the real verdict stream.
        </p>
      </header>

      <div style={{ display: 'flex', gap: 8 }}>
        <input value={task} onChange={(e) => setTask(e.target.value)} disabled={running}
          placeholder="What should the agent do?" style={{ flex: 1 }} aria-label="agent task" />
        <button className="btn-primary" style={{ borderRadius: 8 }} onClick={run} disabled={running || !task.trim()}>
          {running ? 'Running…' : 'Run'}
        </button>
      </div>
      {error && <p style={{ color: 'var(--crit)', fontSize: 14.5 }}>{error}</p>}

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 24, marginTop: 24 }}>
        <div>
          <div className="mono" style={{ fontSize: 12.5, color: 'var(--faint)', letterSpacing: '0.06em', marginBottom: 8 }}>TRACE</div>
          <div className="mono" style={{ border: '1px solid var(--line)', borderRadius: 12, padding: 18, minHeight: 180, fontSize: 13.5, lineHeight: 2 }}>
            {steps.length === 0 && <span style={{ color: 'var(--faint)' }}>Type a task and press Run.</span>}
            {steps.map((s, i) => (
              <div key={i}>
                <span style={{ color: 'var(--faint)' }}>{i + 1}.</span> {s.server}.{s.tool}
                <span style={{ color: 'var(--faint)' }}> {JSON.stringify(s.arguments)}</span>
                {' → '}<strong style={{ color: VERDICT_COLOR[s.verdict] ?? 'var(--ink)' }}>{s.verdict}</strong>
                {s.approval_id && <span style={{ color: 'var(--high)' }}> · approval {s.approval_id}</span>}
                <div style={{ color: 'var(--muted)', paddingLeft: 24, whiteSpace: 'pre-wrap' }}>
                  {(s.observation || '(no output)').slice(0, 220)}
                </div>
              </div>
            ))}
          </div>
          {outcome && (
            <p style={{ marginTop: 12 }}>
              <strong>{outcome}</strong>{' '}
              {session && <Link to={`/graph?session=${session}`} style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                Inspect session {session} in the graph →
              </Link>}
            </p>
          )}
        </div>
        <div>
          <div className="mono" style={{ fontSize: 12.5, color: 'var(--faint)', letterSpacing: '0.06em', marginBottom: 8 }}>
            AVAILABLE TOOLS ({tools.length})
          </div>
          <div style={{ borderTop: '1px solid var(--line)' }}>
            {tools.map((t) => (
              <div key={`${t.server}.${t.tool}`} style={{ padding: '10px 0', borderBottom: '1px solid var(--line)' }}>
                <div className="mono" style={{ fontSize: 13 }}>{t.server}.{t.tool}</div>
                <div style={{ fontSize: 12.5, color: 'var(--faint)' }}>{t.description}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
