import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow';
import 'reactflow/dist/style.css';
import { RiskMeter, SeverityBadge } from '../components/Severity';
import { loadSession, type SessionData } from '../data/provider';

const LANE: Record<string, number> = { SERVER: 0, TOOL: 1, DATA: 2, INSTRUCTION: 2, DESTINATION: 3 };
const TYPES = ['SERVER', 'TOOL', 'DATA', 'INSTRUCTION', 'DESTINATION'];

function label(n: { type: string; [k: string]: unknown }) {
  return `${n.type}: ${String(n.tool ?? n.data_class ?? n.name ?? n.server ?? '')}`.slice(0, 42);
}

export default function GraphExplorer() {
  const [params, setParams] = useSearchParams();
  const session = params.get('session') ?? 'S-DEMO';
  const [data, setData] = useState<SessionData | null>(null);
  const [radial, setRadial] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState<string[] | null>(null);
  const [types, setTypes] = useState<Set<string>>(new Set(TYPES));
  const [suspOnly, setSuspOnly] = useState(false);
  const [tick, setTick] = useState<number>(-1);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  useEffect(() => { loadSession(session).then(setData).catch(() => {}); }, [session]);
  const hot = useMemo(() => new Set((data?.paths ?? []).flatMap((p) => p.node_ids)), [data]);
  const times = useMemo(() => {
    const ts = [...new Set((data?.nodes ?? []).map((n) => String(n.timestamp ?? '')))].sort();
    return ts;
  }, [data]);
  useEffect(() => { setTick(times.length - 1); }, [times]);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setTick((t) => {
      if (t >= times.length - 1) { setPlaying(false); return t; }
      return t + 1;
    }), 600 / speed);
    return () => clearInterval(id);
  }, [playing, speed, times.length]);

  const adj = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const e of data?.edges ?? []) {
      if (!m.has(e.source)) m.set(e.source, new Set());
      if (!m.has(e.target)) m.set(e.target, new Set());
      m.get(e.source)!.add(e.target); m.get(e.target)!.add(e.source);
    }
    return m;
  }, [data]);

  const cutoff = tick >= 0 ? times[tick] : '';
  const visible = useMemo(() => (data?.nodes ?? []).filter((n) => {
    if (!types.has(n.type)) return false;
    if (suspOnly && !hot.has(n.id)) return false;
    if (tick >= 0 && String(n.timestamp ?? '') > cutoff) return false;
    return true;
  }), [data, types, suspOnly, hot, tick, cutoff]);
  const visIds = useMemo(() => new Set(visible.map((n) => n.id)), [visible]);

  const flowNodes: Node[] = useMemo(() => {
    const laneIdx = new Map<string, number>();
    return visible.map((n, i) => {
      const lane = LANE[n.type] ?? 1;
      const order = laneIdx.get(String(lane)) ?? 0;
      laneIdx.set(String(lane), order + 1);
      const pos = radial
        ? { x: 420 + 300 * Math.cos((2 * Math.PI * i) / Math.max(1, visible.length)), y: 320 + 300 * Math.sin((2 * Math.PI * i) / Math.max(1, visible.length)) }
        : { x: order * 220, y: lane * 180 };
      const dim = (focus && !focus.includes(n.id)) || (hovered && hovered !== n.id && !adj.get(hovered)?.has(n.id));
      const isHot = hot.has(n.id);
      return {
        id: n.id, position: pos,
        data: { label: label(n) },
        style: {
          background: isHot ? 'rgba(255,99,111,0.08)' : 'var(--bg-1)',
          color: 'var(--ink)',
          border: isHot ? '1.5px solid var(--crit)' : '1px solid var(--line)',
          borderRadius: 10, padding: '9px 12px', fontSize: 12.5,
          fontFamily: 'var(--font-mono)', opacity: dim ? 0.22 : 1,
        },
      };
    });
  }, [visible, radial, hot, focus, hovered, adj]);

  const flowEdges: Edge[] = useMemo(() => (data?.edges ?? [])
    .filter((e) => visIds.has(e.source) && visIds.has(e.target))
    .map((e, i) => ({
      id: `e${i}`, source: e.source, target: e.target, label: e.type,
      labelStyle: { fill: 'var(--faint)', fontSize: 10, fontFamily: 'var(--font-mono)' },
      labelBgStyle: { fill: 'var(--bg-0)' },
      animated: e.type === 'SENDS' || e.type === 'FLOWS_TO',
      style: { stroke: e.type === 'SENDS' ? 'var(--crit)' : e.type === 'FLOWS_TO' ? 'var(--accent)' : 'rgba(255,255,255,0.22)', strokeWidth: e.type === 'SENDS' ? 2 : 1.2 },
    })), [data, visIds]);

  const sel = data?.nodes.find((n) => n.id === selected) ?? null;
  const selFindings = data?.paths.filter((p) => selected && p.node_ids.includes(selected)) ?? [];

  return (
    <div>
      <header style={{ padding: '56px 0 28px', maxWidth: 720 }}>
        <span className="eyebrow">Inspect</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Graph explorer</h1>
        <p className="sub" style={{ fontSize: 16 }}>One graph per session. The red path is the attack - everything else is context.</p>
      </header>

      <div style={{
        display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center',
        padding: '12px 0', borderTop: '1px solid var(--line)', fontSize: 13.5, color: 'var(--muted)',
      }}>
        <label>Session <input className="mono" value={session}
          onChange={(e) => setParams({ session: e.target.value })} style={{ width: 130, marginLeft: 6 }} /></label>
        <button onClick={() => setRadial((r) => !r)}>{radial ? 'Swimlanes' : 'Radial'}</button>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" checked={suspOnly} onChange={(e) => setSuspOnly(e.target.checked)} /> Suspicious only
        </label>
        <span style={{ display: 'flex', gap: 10 }}>
          {TYPES.map((t) => (
            <label key={t} style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 12.5 }}>
              <input type="checkbox" checked={types.has(t)}
                onChange={() => setTypes((s) => { const n = new Set(s); if (n.has(t)) n.delete(t); else n.add(t); return n; })} /> {t}
            </label>
          ))}
        </span>
      </div>

      <div style={{ border: '1px solid var(--line)', borderRadius: 12, overflow: 'hidden', background: 'var(--bg-0)' }}>
        <div style={{ height: 560 }}>
          <ReactFlow nodes={flowNodes} edges={flowEdges} fitView
            onNodeClick={(_, n) => { setSelected(n.id); setFocus(null); }}
            onNodeMouseEnter={(_, n) => setHovered(n.id)}
            onNodeMouseLeave={() => setHovered(null)}>
            <Background color="rgba(255,255,255,0.05)" gap={28} />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable style={{ background: 'var(--bg-1)' }} />
          </ReactFlow>
        </div>
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', padding: '12px 16px',
          borderTop: '1px solid var(--line)',
        }} aria-label="time replay">
          <button onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'pause replay' : 'play replay'}>
            {playing ? '❚❚' : '▶'}
          </button>
          <input type="range" min={0} max={Math.max(0, times.length - 1)} value={Math.max(0, tick)}
            onChange={(e) => { setTick(Number(e.target.value)); setPlaying(false); }} style={{ flex: 1 }} aria-label="replay position" />
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="replay speed">
            <option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option>
          </select>
          <span className="mono" style={{ fontSize: 12, color: 'var(--faint)', minWidth: 64 }}>
            {tick >= 0 ? times[tick]?.slice(11, 19) : ''}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
        {(data?.paths ?? []).map((p) => (
          <button key={p.pattern} onClick={() => setFocus(focus ? null : p.node_ids)}
            style={{ borderColor: focus ? 'var(--accent)' : 'var(--crit)' }}>
            {focus ? 'Clear focus' : 'Focus'}: <span className="mono">{p.pattern}</span> <RiskMeter score={p.risk} />
          </button>
        ))}
      </div>

      {sel && (
        <aside aria-label="node details" style={{
          marginTop: 16, border: '1px solid var(--line)', borderRadius: 12, padding: 20, maxWidth: 640,
        }}>
          <div className="mono" style={{ fontSize: 15, fontWeight: 600 }}>{label(sel)}</div>
          <div className="mono" style={{ fontSize: 12.5, color: 'var(--faint)', marginTop: 6 }}>
            {String(sel.session_id ?? session)} · {String(sel.timestamp ?? '').slice(11, 19)}
            {sel.trust ? ` · trust ${String(sel.trust)}` : ''}
            {sel.data_class ? ` · ${String(sel.data_class)}` : ''}
          </div>
          {selFindings.map((f) => (
            <p key={f.pattern} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <SeverityBadge level={f.severity as 'CRITICAL' | 'HIGH'} /> <RiskMeter score={f.risk} />
            </p>
          ))}
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button onClick={() => navigator.clipboard?.writeText(sel.id).catch(() => {})}>Copy ID</button>
            <button onClick={() => setSelected(null)}>Close</button>
          </div>
        </aside>
      )}

      <details style={{ marginTop: 16 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--faint)', fontSize: 13.5 }}>Node list (keyboard access)</summary>
        {visible.map((n) => (
          <button key={n.id} onClick={() => setSelected(n.id)}
            style={{ display: 'block', margin: '6px 0', fontSize: 13, border: 'none', padding: '4px 0', color: 'var(--muted)' }}
            className="mono">{label(n)}</button>
        ))}
      </details>
    </div>
  );
}
