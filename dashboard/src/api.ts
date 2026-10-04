export interface GraphNode { id: string; type: string; [k: string]: unknown }
export interface GraphEdge { source: string; target: string; type: string }
export interface AttackPath { pattern: string; severity: string; risk: number; tools: string[]; node_ids: string[] }
export interface Alert extends AttackPath { policy: string; verdict: string; explanation: string }

export async function fetchGraph(session: string) {
  const r = await fetch(`/api/graph?session=${encodeURIComponent(session)}`);
  return (await r.json()) as { nodes: GraphNode[]; edges: GraphEdge[]; paths: AttackPath[] };
}

export async function fetchAlerts(session: string) {
  const r = await fetch(`/api/alerts?session=${encodeURIComponent(session)}`);
  return (await r.json()) as { alerts: Alert[] };
}

export async function grantApproval(approvalId: string) {
  const r = await fetch('/approvals/grant', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approval_id: approvalId }),
  });
  return (await r.json()) as { granted: boolean };
}
