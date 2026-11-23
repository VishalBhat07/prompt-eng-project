import { MarkerType, type Edge, type Node } from 'reactflow';
import type { SessionData } from './types';

const AGENT_ID = 'ui:agent';

// These links explain who exchanged an event. They are never policy evidence.
export function agentOverlay(
  data: SessionData,
  nodes: Node[],
  nodeIdForEvent: (tool: string, eventId: string) => string,
): { node: Node; edges: Edge[] } | null {
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
  return {
    node: {
      id: AGENT_ID,
      position: { x: (Math.min(...xs) + Math.max(...xs)) / 2,
                  y: Math.min(...nodes.map((node) => node.position.y)) - 105 },
      data: { label: isAgent ? (model ? `Agent · ${model}` : 'Agent') : 'Session caller' },
      style: { width: 180, overflowWrap: 'anywhere', background: 'var(--bg-1)',
        color: 'var(--ink)', border: `2px solid ${color}` },
    },
    edges: exchanges.map(({ id, proposed }) => ({
      id: `${AGENT_ID}:${id}`,
      source: proposed ? AGENT_ID : id,
      target: proposed ? id : AGENT_ID,
      label: exchanges.length <= 12 ? (proposed ? 'Proposes' : 'Receives output') : undefined,
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: { stroke: color, opacity: 0.7 },
      labelStyle: { fill: 'var(--ink)', fontSize: 10 },
      labelBgStyle: { fill: 'var(--bg-0)' },
    })),
  };
}
