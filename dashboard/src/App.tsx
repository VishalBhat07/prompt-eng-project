import { useCallback, useEffect, useState } from 'react';
import GraphView from './GraphView';
import Alerts from './Alerts';
import { fetchAlerts, fetchGraph, type Alert, type GraphEdge, type GraphNode } from './api';

export default function App() {
  const [session, setSession] = useState('S-CHAIN');
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [hot, setHot] = useState<Set<string>>(new Set());

  const refresh = useCallback(async () => {
    const g = await fetchGraph(session);
    setNodes(g.nodes);
    setEdges(g.edges);
    setHot(new Set(g.paths.flatMap((p) => p.node_ids)));
    setAlerts((await fetchAlerts(session)).alerts);
  }, [session]);

  useEffect(() => {
    refresh();
    const ws = new WebSocket(`ws://${location.host}/ws/events`);
    ws.onmessage = () => refresh();
    const t = setInterval(refresh, 5000);
    return () => { ws.close(); clearInterval(t); };
  }, [refresh]);

  return (
    <div style={{ fontFamily: 'system-ui', padding: 16, maxWidth: 1100 }}>
      <h1>CrossToolGuard</h1>
      <label>
        Session:{' '}
        <input value={session} onChange={(e) => setSession(e.target.value)} style={{ width: 200 }} />
        <button onClick={refresh} style={{ marginLeft: 8 }}>Refresh</button>
      </label>
      <h2>Attack graph (live)</h2>
      <GraphView nodes={nodes} edges={edges} hot={hot} />
      <h2>Findings</h2>
      <Alerts alerts={alerts} onGranted={refresh} />
    </div>
  );
}
