export interface MCPToolDefinition {
  name: string;
  title?: string | null;
  description?: string | null;
  inputSchema?: Record<string, unknown>;
  outputSchema?: Record<string, unknown> | null;
  annotations?: Record<string, unknown> | null;
  _registry?: {
    version: number;
    description_hash: string;
    schema_hash: string;
    definition_hash: string;
    capabilities: string[];
    integrity_status: 'NEW' | 'OK' | 'MODIFIED' | 'APPROVED' | 'REMOVED';
  };
  [key: string]: unknown;
}
export interface MCPInventory {
  server_id: string;
  transport: string;
  endpoint_url: string | null;
  server_info: { name?: string; version?: string } | null;
  protocol_version: string | null;
  instructions: string | null;
  capabilities: Record<string, unknown>;
  inventory_hash: string;
  version: number;
  integrity_status: 'NEW' | 'OK' | 'MODIFIED' | 'APPROVED';
  first_seen?: string | null;
  last_seen?: string | null;
  assessment?: MCPAssessment | null;
  tools: MCPToolDefinition[];
  removed_tools: { name: string; version: number; definition_hash: string; integrity_status: 'REMOVED' }[];
}

export interface MCPAssessmentFinding {
  id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  confidence: 'high' | 'medium' | 'low';
  evidence_path: string;
  evidence: string;
  explanation: string;
  recommendation: string;
  risk_weight: number;
}

export interface MCPToolAssessment {
  tool: string;
  definition_hash: string;
  capabilities: string[];
  risk_score: number;
  risk_band: string;
  findings: MCPAssessmentFinding[];
}

export interface MCPAssessment {
  assessment_type: 'metadata_only';
  risk_score: number;
  risk_band: string;
  tool_count: number;
  finding_count: number;
  server_findings: MCPAssessmentFinding[];
  tools: MCPToolAssessment[];
  coverage: Record<string, boolean>;
  limitations: string[];
}

export async function fetchInventories(): Promise<MCPInventory[]> {
  const r = await fetch('/api/registry/inventories');
  if (!r.ok) throw new Error(`Inventory request failed (${r.status})`);
  const body = await r.json() as { inventories: MCPInventory[] };
  return body.inventories;
}

export async function inspectRemoteServer(input: { server_id: string; url: string; bearer_token?: string }) {
  const r = await fetch('/api/registry/inspect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  const body = await r.json() as { inventory?: MCPInventory; scan_status?: string; detail?: string };
  if (!r.ok) throw new Error(body.detail || `Inventory request failed (${r.status})`);
  return body;
}

export async function approveInventory(input: { server_id: string; inventory_hash: string }) {
  const r = await fetch('/api/registry/approve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  const body = await r.json() as { inventory?: MCPInventory; approved?: boolean; detail?: string };
  if (!r.ok) throw new Error(body.detail || `Inventory approval failed (${r.status})`);
  return body;
}
