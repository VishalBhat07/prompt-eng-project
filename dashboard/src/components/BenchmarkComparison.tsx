import { useEffect, useState } from 'react';
import ReactFlow, { Background, Controls, MarkerType, type Edge, type Node } from 'reactflow';
import 'reactflow/dist/style.css';

interface Observation {
  event_id: string; server: string; tool: string; event_type: string;
  data_class: string; parent_id: string | null; output_preview: string;
}
interface ReplayCase {
  id: string; variant: string; expected: { alert: boolean; verdict: string }; events: Observation[];
  single_output: { alert: boolean; flagged_event_ids: string[] };
  full_graph: { alert: boolean; verdict: string; signal_ids: string[]; findings: { pattern: string; path: string[] }[] };
}
interface Pair { id: string; title: string; change: string; cases: ReplayCase[] }
interface Counts { detections: number; positive_cases: number; false_alerts: number; control_cases: number }
interface Comparison { pairs: Pair[]; summary: { single_output: Counts; full_graph: Counts } }

function ReplayGraph({ row, full }: { row: ReplayCase; full: boolean }) {
  const servers = [...new Set(row.events.map((event) => event.server))];
  const path = row.full_graph.findings.flatMap((finding) => finding.path).concat(row.full_graph.signal_ids);
  const highlighted = new Set(row.events.filter((event) => full
    ? path.some((id) => id.endsWith(':' + event.event_id) || id.endsWith(':' + event.event_id + ':arguments'))
    : row.single_output.flagged_event_ids.includes(event.event_id)).map((event) => event.event_id));
  const title = full ? 'CrossToolGuard session graph' : 'Single-output detector';
  const alert = full ? row.full_graph.alert : row.single_output.alert;
  const nodes: Node[] = servers.map((server, index) => ({
    id: `lane-${server}`, position: { x: index * 210, y: 0 }, type: 'input',
    data: { label: `Server · ${server}` },
    style: { color: 'var(--ink)', background: 'var(--wash)', borderColor: 'var(--line)', width: 188 },
  }));
  const edges: Edge[] = [];
  row.events.forEach((event, index) => {
    nodes.push({
      id: event.event_id, position: { x: servers.indexOf(event.server) * 210, y: 65 + index * 86 },
      data: { label: <><strong>{index + 1}. {event.tool}</strong><br />
        {event.event_type === 'TOOL_CALL' ? 'Proposed call' : `Output · ${event.data_class}`}</> },
      style: { width: 188, overflowWrap: 'anywhere', color: 'var(--ink)', background: 'var(--bg-0)',
        borderColor: highlighted.has(event.event_id) ? 'var(--crit)' : 'var(--line)' },
    });
    if (full && event.parent_id) {
      const onPath = highlighted.has(event.event_id) && highlighted.has(event.parent_id);
      const color = onPath ? 'var(--crit)' : 'var(--muted)';
      edges.push({ id: `${event.parent_id}-${event.event_id}`, source: event.parent_id, target: event.event_id,
        label: 'Recorded parent', markerEnd: { type: MarkerType.ArrowClosed, color },
        style: { stroke: color, strokeWidth: onPath ? 2 : 1 } });
    }
  });
  return <article className="card" style={{ minWidth: 0, padding: 12 }}>
    <h4>{title}</h4>
    <p>{alert ? 'Alert' : 'No alert'}{full && ` · Verdict ${row.full_graph.verdict}`}</p>
    <div style={{ height: 330 }} role="group" aria-label={title}>
      <ReactFlow key={row.id} nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.17 }}
        nodesDraggable={false} nodesConnectable={false} zoomOnScroll={false}>
        <Background /><Controls showInteractive={false} />
      </ReactFlow>
    </div>
    <details><summary>Event evidence</summary>
      <ol>{row.events.map((event) => <li key={event.event_id}>
        {event.server}/{event.tool} · {event.event_type === 'TOOL_CALL' ? 'Proposed call' : event.data_class}
        {full && event.parent_id && ` · parent event ${row.events.findIndex((item) => item.event_id === event.parent_id) + 1}`}
        {event.output_preview && ` · ${event.output_preview}`}
      </li>)}</ol>
      {full && row.full_graph.findings.map((finding, index) => <p key={index}>{finding.pattern}</p>)}
    </details>
  </article>;
}

export default function BenchmarkComparison() {
  const [report, setReport] = useState<Comparison>();
  const [error, setError] = useState(false);
  const [pairId, setPairId] = useState('');
  const [variant, setVariant] = useState('linked');
  useEffect(() => {
    fetch('/data/matched-comparison-v1.json').then((response) => {
      if (!response.ok) throw new Error('Could not load matched comparisons');
      return response.json();
    }).then(setReport).catch(() => setError(true));
  }, []);
  const pair = report?.pairs.find((item) => item.id === pairId) ?? report?.pairs[0];
  const row = pair?.cases.find((item) => item.variant === variant);
  return <section style={{ marginBottom: 36 }}>
    <h2>Matched replay · Tool call comparison</h2>
    <p>Each pair changes one recorded fact. The same synthetic events feed both methods.</p>
    {error && <p role="alert">The comparison artifact could not be loaded.</p>}
    {!report && !error && <p role="status">Loading matched comparisons…</p>}
    {report && pair && row && <>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead><tr><th>Method</th><th>Positive records flagged</th><th>False alerts on controls</th></tr></thead>
          <tbody>{([['Single-output detector', report.summary.single_output],
            ['CrossToolGuard session graph', report.summary.full_graph]] as const).map(([label, counts]) =>
            <tr key={label}><td>{label}</td><td>{counts.detections} / {counts.positive_cases}</td>
              <td>{counts.false_alerts} / {counts.control_cases}</td></tr>)}</tbody>
        </table>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, margin: '16px 0' }}>
        <label style={{ minWidth: 0, maxWidth: '100%' }}>Case pair <select style={{ maxWidth: '100%' }} value={pair.id} onChange={(event) => setPairId(event.target.value)}>
          {report.pairs.map((item) => <option value={item.id} key={item.id}>{item.id} · {item.title}</option>)}
        </select></label>
        <label>Variant <select value={variant} onChange={(event) => setVariant(event.target.value)}>
          <option value="linked">Positive record</option><option value="control">Benign control</option>
        </select></label>
        <a href="/data/matched-comparison-v1.json" download>Download case evidence</a>
      </div>
      <p>{row.id} · Changed field: {pair.change} · Expected {row.expected.alert ? 'alert' : 'no alert'} / {row.expected.verdict}</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))', gap: 12 }}>
        <ReplayGraph row={row} full={false} /><ReplayGraph row={row} full />
      </div>
    </>}
  </section>;
}
