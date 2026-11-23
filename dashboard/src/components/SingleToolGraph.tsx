import ReactFlow, { Background, Controls, type Edge, type Node } from 'reactflow';
import type { SessionData } from '../data/types';
import { agentOverlay } from '../data/agentGraph';

export default function SingleToolGraph({ data }: { data: SessionData }) {
  const baseline = data.single_tool;
  const flags = new Set(baseline?.status === 'ready' ? baseline.flagged_event_ids : []);
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const servers = new Set<string>();
  const blocked = new Set(data.blocks?.map((block) => block.call_node_id));

  data.events.forEach((event, index) => {
    const { event_id: eventId, server, tool, event_type: kind } = event;
    if (typeof eventId !== 'string' || typeof server !== 'string' || typeof tool !== 'string') return;
    if (kind !== 'TOOL_CALL' && kind !== 'TOOL_OUTPUT') return;
    const serverId = `server:${server}`;
    const x = index * 205;
    if (!servers.has(server)) {
      servers.add(server);
      nodes.push({ id: serverId, position: { x, y: 0 }, type: 'input', data: { label: server } });
    }
    const flag = flags.has(eventId);
    const description = kind === 'TOOL_OUTPUT' ? 'Output' :
      blocked.has(`tool:${tool}:${eventId}`) ? 'Proposed call · blocked by gateway' : 'Proposed call';
    nodes.push({
      id: eventId, position: { x, y: 110 },
      data: { label: <><strong>{tool}</strong><br />{description}{flag && <><br />Suspicious output</>}</> },
      style: { width: 180, overflowWrap: 'anywhere', color: 'var(--ink)', background: 'var(--bg-1)',
        borderColor: flag ? 'var(--crit)' : 'var(--line)' },
    });
    edges.push({ id: `edge:${eventId}`, source: serverId, target: eventId, label: 'Server' });
  });
  const agent = agentOverlay(data, nodes, (_tool, eventId) => eventId);
  if (agent) {
    nodes.push(agent.node);
    edges.push(...agent.edges);
  }

  return <section aria-label="Single-tool detector graph" style={{ minWidth: 0 }}>
    <h2>Single-tool detector</h2>
    <p>Each output preview is checked on its own. Accent arrows show the agent’s proposals and returned outputs.</p>
    {baseline?.status === 'ready'
      ? <p>{flags.size} flagged / {baseline.evaluated} output previews checked</p>
      : <p role="status">{baseline
        ? 'The gateway could not assess the saved output previews. Check the gateway analyzer settings.'
        : 'The running gateway did not return a detector result. Restart the gateway from this project, then refresh this page.'}</p>}
    {nodes.length > 0
      ? <div style={{ height: 560, border: '1px solid var(--line)', borderRadius: 12, overflow: 'hidden' }}>
        <ReactFlow key={data.session} nodes={nodes} edges={edges} fitView nodesDraggable={false}
          nodesConnectable={false} zoomOnScroll={false}>
          <Background /><Controls showInteractive={false} />
        </ReactFlow>
      </div>
      : <p>No tool events to display.</p>}
  </section>;
}
