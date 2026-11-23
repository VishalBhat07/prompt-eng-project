import { MarkerType, type Edge, type Node } from 'reactflow';
import type { SessionData } from './types';

const AGENT_ID = 'ui:agent';
const GATEWAY_ID = 'ui:gateway';

export function toolEventSteps(events: SessionData['events'] | undefined): Map<string, number> {
  const steps = new Map<string, number>();
  for (const event of events ?? []) {
    if (typeof event.event_id === 'string' && typeof event.tool === 'string'
        && (event.event_type === 'TOOL_CALL' || event.event_type === 'TOOL_OUTPUT')) {
      steps.set(event.event_id, steps.size + 1);
    }
  }
  return steps;
}

// These links explain who exchanged an event. They are never policy evidence.
export function agentOverlay(
  data: SessionData,
  nodes: Node[],
  nodeIdForEvent: (tool: string, eventId: string) => string,
  throughGateway = false,
): { nodes: Node[]; edges: Edge[] } | null {
  const visible = new Map(nodes.map((node) => [node.id, node.position]));
  const exchanges = data.events.flatMap((event) => {
    if (typeof event.event_id !== 'string' || typeof event.tool !== 'string') return [];
    const kind = event.event_type;
    if (kind !== 'TOOL_CALL' && kind !== 'TOOL_OUTPUT') return [];
    const id = nodeIdForEvent(event.tool, event.event_id);
    const position = visible.get(id);
    return position ? [{ id, position, proposed: kind === 'TOOL_CALL' }] : [];
  });
  if (exchanges.length === 0) return null;
  const xs = exchanges.map(({ position }) => position.x);
  const isAgent = data.session.startsWith('agent-') || Boolean(data.report?.provider);
  const model = data.report?.model;
  const color = 'var(--accent)';
  const x = (Math.min(...xs) + Math.max(...xs)) / 2;
  const y = Math.min(...nodes.map((node) => node.position.y)) - 105;
  const endpoint = throughGateway ? GATEWAY_ID : AGENT_ID;
  const overlayNodes: Node[] = [{
      id: AGENT_ID,
      position: { x, y: throughGateway ? y - 105 : y },
      data: { label: isAgent ? (model ? `Agent · ${model}` : 'Agent') : 'Session caller' },
      style: { width: 180, overflowWrap: 'anywhere', background: 'var(--bg-1)',
        color: 'var(--ink)', border: `2px solid ${color}` },
  }];
  const blocked = new Set(data.blocks?.map((block) => block.call_node_id));
  const edges: Edge[] = exchanges.map(({ id, proposed }) => {
    const stopped = throughGateway && blocked.has(id);
    const stroke = stopped ? 'var(--crit)' : color;
    const description = throughGateway
      ? (proposed ? (stopped ? 'Checks · BLOCK' : 'Checks proposal') : 'Receives output')
      : (proposed ? 'Proposes' : 'Receives output');
    return {
      id: `${endpoint}:${id}`,
      source: proposed ? endpoint : id,
      target: proposed ? id : endpoint,
      label: exchanges.length <= 12 || stopped ? description : undefined,
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke },
      style: { stroke, opacity: 0.7 },
      labelStyle: { fill: 'var(--ink)', fontSize: 10 },
      labelBgStyle: { fill: 'var(--bg-0)' },
    };
  });
  if (throughGateway) {
    overlayNodes.push({
      id: GATEWAY_ID, position: { x, y },
      data: { label: 'CrossToolGuard gateway' },
      style: { width: 180, background: 'var(--bg-1)', color: 'var(--ink)', border: `2px solid ${color}` },
    });
    const arrow = { type: MarkerType.ArrowClosed, color };
    edges.push({
      id: `${AGENT_ID}:${GATEWAY_ID}`, source: AGENT_ID, target: GATEWAY_ID,
      label: 'Proposals and replies', markerEnd: arrow,
      markerStart: exchanges.some(({ proposed }) => !proposed) ? arrow : undefined,
      style: { stroke: color }, labelStyle: { fill: 'var(--ink)', fontSize: 10 },
      labelBgStyle: { fill: 'var(--bg-0)' },
    });
  }
  return { nodes: overlayNodes, edges };
}
