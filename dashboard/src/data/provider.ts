import type { AttackPath, SessionData, SessionSummary } from './types';

export type { AttackPath, SessionData, SessionSummary };

async function loadSession(id: string): Promise<SessionData> {
  const r = await fetch(`/api/sessions/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error(`Session ${id} could not be loaded (${r.status})`);
  const d = (await r.json()) as SessionData;
  return { ...d, session: id };
}

export async function listSessions(): Promise<SessionSummary[]> {
  const r = await fetch('/api/sessions');
  if (!r.ok) throw new Error(`Session list could not be loaded (${r.status})`);
  const body = await r.json() as { sessions: SessionSummary[] };
  return body.sessions;
}

export { loadSession };
