export interface GraphNode { id: string; type: string; [k: string]: unknown }
export interface GraphEdge { source: string; target: string; type: string }
export interface AttackPath {
  pattern: string; severity: 'CRITICAL' | 'HIGH'; risk: number;
  tools: string[]; node_ids: string[]; policy: string; verdict: string; explanation: string;
}
export interface SessionSummary {
  id: string; tools: number; events: number; findings: number;
  blocked: number; maxRisk: number; status: 'CLEAN' | 'HIGH' | 'CRITICAL';
}
export interface SessionData {
  session: string; nodes: GraphNode[]; edges: GraphEdge[];
  paths: AttackPath[]; events: Record<string, unknown>[];
}
export interface Approval { id: string; session: string; tool: string; risk: number; explanation: string }
export interface BenchDoc {
  cases: number; detection_rate: number; false_positive_rate: number;
  cross_tool_gain: string[];
  baselines: Record<string, { caught: number; ids: string[] }>;
  ablation: Record<string, { caught: number; ids: string[] }>;
  latency: { mean_s: number; p95_s: number; n: number };
}
