export interface GraphNode { id: string; type: string; [k: string]: unknown }
export interface GraphEdge { source: string; target: string; type: string }
export interface AttackPath {
  pattern: string; severity: 'CRITICAL' | 'HIGH'; risk: number;
  tools: string[]; node_ids: string[]; policy: string; verdict: string; explanation: string;
}
export interface SessionSummary {
  signals?: number; possible_paths?: number; outcome?: string | null;
  id: string; tools: number; events: number; findings: number;
  blocked: number; maxRisk: number; status: 'CLEAN' | 'HIGH' | 'CRITICAL'; run_status?: string | null;
}
export interface SessionData {
  session: string; nodes: GraphNode[]; edges: GraphEdge[];
  paths: AttackPath[]; events: Record<string, unknown>[];
  potential_paths?: { source: string; destination: string; trigger_events: { event_id: string; tool: string; server: string }[]; explanation: string }[];
  signals?: { node_id: string; origin_tool: string; explanation: string }[];
  report?: { outcome: string; provider: string; model: string; policy?: string;
    calls: { tool: string; verdict?: string }[] } | null;
}
export interface Approval { id: string; session: string; tool: string; risk: number; explanation: string }
export interface BenchDoc {
  cases: number; attack_cases: number; benign_cases: number;
  detection_rate: number; false_positive_rate: number;
  cross_tool_gain: string[];
  baselines: Record<string, { caught: number; ids: string[] }>;
  ablation: Record<string, { caught: number; ids: string[] }>;
  latency: { mean_s: number; p95_s: number; n: number };
}
