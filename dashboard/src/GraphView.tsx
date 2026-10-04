import ReactFlow, { Background, Controls, Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import type { GraphNode, GraphEdge } from './api';

const LANE_Y: Record<string, number> = { SERVER: 0, TOOL: 140, DATA: 280, INSTRUCTION: 280, DESTINATION: 420 };
const TYPE_COLOR: Record<string, string> = {
  TOOL: '#dbeafe', SERVER: '#e5e7eb', DATA: '#fef3c7',
  INSTRUCTION: '#fecaca', DESTINATION: '#fbcfe8',
};

export default function GraphView({ nodes, edges, hot }: { nodes: GraphNode[]; edges: GraphEdge[]; hot: Set<string> }) {
  const flowNodes: Node[] = nodes.map((n, i) => ({
    id: n.id,
    position: { x: (i % 8) * 190, y: LANE_Y[n.type] ?? 140 },
    data: { label: `${n.type}: ${String(n.tool ?? n.data_class ?? n.name ?? n.server ?? n.id.slice(0, 18))}` },
    style: {
      background: TYPE_COLOR[n.type] ?? '#fff',
      border: hot.has(n.id) ? '3px solid #dc2626' : '1px solid #555',
      borderRadius: 8, padding: 8, fontSize: 12,
    },
  }));
  const flowEdges: Edge[] = edges.map((e, i) => ({
    id: `e${i}`, source: e.source, target: e.target, label: e.type,
    animated: e.type === 'SENDS' || e.type === 'FLOWS_TO',
    style: { stroke: e.type === 'SENDS' ? '#dc2626' : '#555' },
  }));
  return (
    <div style={{ height: 520, border: '1px solid #ccc' }}>
      <ReactFlow nodes={flowNodes} edges={flowEdges} fitView>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
