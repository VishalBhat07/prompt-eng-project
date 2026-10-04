import type { AttackPath, SessionData, SessionSummary } from './types';

export type { AttackPath, SessionData, SessionSummary };

async function loadSession(id: string): Promise<SessionData> {
  const file = id === 'S-DEMO' ? 'session-demo.json' : 'session-demo.json';
  const r = await fetch(`/data/${file}`);
  const d = (await r.json()) as SessionData;
  return { ...d, session: id };
}

const CLEAN: SessionSummary = {
  id: 'S-N1', tools: 2, events: 3, findings: 0, blocked: 0, maxRisk: 0.04, status: 'CLEAN',
};

export async function listSessions(): Promise<SessionSummary[]> {
  const demo = await loadSession('S-DEMO');
  const tools = new Set(demo.nodes.filter((n) => n.type === 'TOOL').map((n) => String(n.tool)));
  return [
    {
      id: 'S-DEMO', tools: tools.size, events: demo.events.length,
      findings: demo.paths.length, blocked: 1,
      maxRisk: Math.max(...demo.paths.map((p) => p.risk)),
      status: 'CRITICAL',
    },
    CLEAN,
  ];
}

export { loadSession };
