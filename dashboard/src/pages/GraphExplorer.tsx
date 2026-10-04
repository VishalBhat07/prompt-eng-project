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
      const k = `${lane}-${laneIdx.get(String(lane)) ?? 0}`;
      laneIdx.set(String(lane), (laneIdx.get(String(lane)) ?? 0) + 1);
      const order = parseInt(k.split('-')[1], 10);
      const pos = radial
        ? { x: 400 + 280 * Math.cos((2 * Math.PI * i) / Math.max(1, visible.length)), y: 300 + 280 * Math.sin((2 * Math.PI * i) / Math.max(1, visible.length)) }
        : { x: order * 210, y: lane * 175 };
      const dim = (focus && !focus.includes(n.id)) || (hovered && hovered !== n.id && !adj.get(hovered)?.has(n.id));
      return {
        id: n.id, position: pos,
        data: { label: label(n) },
        style: {
          background: 'var(--bg-2)', color: 'var(--ink)',
          border: hot.has(n.id) ? '3px solid var(--crit)' : '1px solid rgba(255,255,255,0.2)',
          borderRadius: 8, padding: 8, fontSize: 12, opacity: dim ? 0.25 : 1,
        },
      };
    });
  }, [visible, radial, hot, focus, hovered, adj]);

  const flowEdges: Edge[] = useMemo(() => (data?.edges ?? [])
    .filter((e) => visIds.has(e.source) && visIds.has(e.target))
    .map((e, i) => ({
      id: `e${i}`, source: e.source, target: e.target, label: e.type,
      animated: e.type === 'SENDS' || e.type === 'FLOWS_TO',
      style: { stroke: e.type === 'SENDS' ? 'var(--crit)' : e.type === 'FLOWS_TO' ? 'var(--accent)' : '#666' },
    })), [data, visIds]);

  const sel = data?.nodes.find((n) => n.id === selected) ?? null;
  const selFindings = data?.paths.filter((p) => selected && p.node_ids.includes(selected)) ?? [];

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <h1 style={{ margin: 0 }}>Graph explorer</h1>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>Session <input className="mono" value={session}
          onChange={(e) => setParams({ session: e.target.value })} style={{ width: 140 }} /></label>
        <button onClick={() => setRadial((r) => !r)}>{radial ? 'Swimlanes' : 'Radial'}</button>
        <label><input type="checkbox" checked={suspOnly} onChange={(e) => setSuspOnly(e.target.checked)} /> Suspicious only</label>
        {TYPES.map((t) => (
          <label key={t} style={{ fontSize: 13 }}>
            <input type="checkbox" checked={types.has(t)}
              onChange={() => setTypes((s) => { const n = new Set(s); if (n.has(t)) n.delete(t); else n.add(t); return n; })} /> {t}
          </label>
        ))}
      </div>
      <div style={{ height: 480, border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8 }}>
        <ReactFlow nodes={flowNodes} edges={flowEdges} fitView
          onNodeClick={(_, n) => { setSelected(n.id); setFocus(null); }}
          onNodeMouseEnter={(_, n) => setHovered(n.id)}
          onNodeMouseLeave={() => setHovered(null)}>
          <Background color="rgba(255,255,255,0.06)" />
          <Controls /><MiniMap pannable zoomable />
        </ReactFlow>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }} aria-label="time replay">
        <button onClick={() => setPlaying((p) => !p)}>{playing ? 'Pause' : 'Play'}</button>
        <input type="range" min={0} max={Math.max(0, times.length - 1)} value={Math.max(0, tick)}
          onChange={(e) => { setTick(Number(e.target.value)); setPlaying(false); }} style={{ flex: 1 }} />
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="replay speed">
          <option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option>
        </select>
        <span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>{tick >= 0 ? times[tick]?.slice(11, 19) : ''}</span>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => setFocus(null)}>Clear focus</button>
        {(data?.paths ?? []).map((p) => (
          <button key={p.pattern} onClick={() => setFocus(p.node_ids)}
            style={{ borderColor: 'var(--crit)' }}>
            Focus: {p.pattern} <RiskMeter score={p.risk} />
          </button>
        ))}
      </div>
      {sel && (
        <aside className="card" aria-label="node details" style={{ padding: 16 }}>
          <h3 className="mono" style={{ marginTop: 0 }}>{label(sel)}</h3>
          <div style={{ fontSize: 14, color: 'var(--muted)' }}>
            session {String(sel.session_id ?? session)} · {String(sel.timestamp ?? '').slice(11, 19)}
            {sel.trust ? ` · trust ${String(sel.trust)}` : ''}
            {sel.data_class ? ` · ${String(sel.data_class)}` : ''}
          </div>
          {selFindings.map((f) => (
            <p key={f.pattern}><SeverityBadge level={f.severity as 'CRITICAL' | 'HIGH'} /> {f.pattern} <RiskMeter score={f.risk} /></p>
          ))}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => navigator.clipboard?.writeText(sel.id).catch(() => {})}>Copy ID</button>
            <button onClick={() => setSelected(null)}>Close</button>
          </div>
        </aside>
      )}
      <details>
        <summary style={{ cursor: 'pointer', color: 'var(--muted)' }}>Node list (keyboard access)</summary>
        {visible.map((n) => (
          <button key={n.id} onClick={() => setSelected(n.id)}
            style={{ display: 'block', margin: '4px 0', fontSize: 13 }} className="mono">{label(n)}</button>
        ))}
      </details>
    </div>
  );
}
