import { useEffect, useState, type FormEvent } from 'react';
import { setInventoryApproval, fetchInventories, inspectRemoteServer, type MCPInventory, type MCPToolDefinition } from '../api';

function Definition({ tool }: { tool: MCPToolDefinition }) {
  const [open, setOpen] = useState(false);
  return (
    <article style={{ padding: '18px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <strong className="mono" style={{ fontSize: 14 }}>{tool.name}</strong>
        {tool.title && <span style={{ color: 'var(--muted)', fontSize: 14 }}>{tool.title}</span>}
        {tool._registry && <span className="mono" style={{ color: tool._registry.integrity_status === 'MODIFIED' ? 'var(--high)' : 'var(--faint)', fontSize: 11 }}>
          {tool._registry.integrity_status} · v{tool._registry.version}
        </span>}
        <button style={{ marginLeft: 'auto', fontSize: 12 }} onClick={() => setOpen(!open)}>
          {open ? 'Hide definition' : 'Inspect definition'}
        </button>
      </div>
      <p style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.6, marginTop: 8, whiteSpace: 'pre-wrap' }}>
        {tool.description || 'No description provided.'}
      </p>
      {open && (
        <pre className="card mono" style={{ marginTop: 14, padding: 16, overflowX: 'auto', fontSize: 12, lineHeight: 1.6 }}>
          {JSON.stringify(tool, null, 2)}
        </pre>
      )}
    </article>
  );
}

function Assessment({ inventory }: { inventory: MCPInventory }) {
  const report = inventory.assessment;
  if (!report) return (
    <div className="hairline" style={{ padding: 14, marginTop: 16, color: 'var(--muted)', fontSize: 13 }}>
      No saved assessment is available for this snapshot.
    </div>
  );
  const allFindings = [
    ...report.server_findings.map((finding) => ({ tool: 'Server instructions', finding })),
    ...report.tools.flatMap((tool) => tool.findings.map((finding) => ({ tool: tool.tool, finding }))),
  ];
  const riskColor = report.risk_band === 'CRITICAL' ? 'var(--crit)' :
    report.risk_band === 'HIGH' ? 'var(--high)' : report.risk_band === 'MEDIUM' ? 'var(--warn)' : 'var(--clean)';
  return (
    <section className="hairline" style={{ padding: 16, marginTop: 18 }}>
      <div style={{ display: 'flex', gap: 14, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <strong style={{ color: riskColor, fontSize: 14 }}>Metadata review: {report.risk_band}</strong>
        <span className="mono" style={{ color: 'var(--muted)', fontSize: 12 }}>
          score {report.risk_score.toFixed(2)} · {report.finding_count} findings
        </span>
        <span style={{ color: 'var(--faint)', fontSize: 12 }}>Heuristic review; not a safety certification.</span>
      </div>
      {allFindings.length > 0 ? (
        <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
          {allFindings.map(({ tool, finding }, index) => (
            <article key={`${tool}-${finding.id}-${index}`} style={{ borderLeft: `3px solid ${finding.severity === 'CRITICAL' ? 'var(--crit)' : finding.severity === 'HIGH' ? 'var(--high)' : 'var(--warn)'}`, padding: '4px 0 4px 12px' }}>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'baseline' }}>
                <strong style={{ fontSize: 13 }}>{finding.severity} · {tool}</strong>
                <span className="mono" style={{ color: 'var(--faint)', fontSize: 11 }}>{finding.id} · confidence {finding.confidence}</span>
              </div>
              <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 5 }}>{finding.explanation}</p>
              <p className="mono" style={{ color: 'var(--faint)', fontSize: 11, marginTop: 5, overflowWrap: 'anywhere' }}>
                Evidence at {finding.evidence_path}: {finding.evidence}
              </p>
              <p style={{ fontSize: 12, marginTop: 5 }}>{finding.recommendation}</p>
            </article>
          ))}
        </div>
      ) : <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 12 }}>No configured metadata rules matched. This does not establish safe behavior.</p>}
      <details style={{ marginTop: 12 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--muted)', fontSize: 12 }}>Coverage and limitations</summary>
        <ul style={{ color: 'var(--muted)', fontSize: 12, lineHeight: 1.7, paddingLeft: 20 }}>
          {Object.entries(report.coverage).map(([key, covered]) => <li key={key}>{key.replace(/_/g, ' ')}: {covered ? 'reviewed' : 'not reviewed'}</li>)}
          {report.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
        </ul>
      </details>
    </section>
  );
}

function ServerCard({ inventory, approving, onApprove }: {
  inventory: MCPInventory;
  approving: boolean;
  onApprove: (inventory: MCPInventory) => void;
}) {
  const [open, setOpen] = useState(false);
  const displayName = inventory.server_info?.name || inventory.server_id;
  return (
    <section className="card" style={{ padding: 22 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 240, flex: 1 }}>
          <h2 style={{ fontSize: 20 }}>{displayName}</h2>
          <p className="mono" style={{ color: 'var(--muted)', fontSize: 12, marginTop: 6 }}>{inventory.server_id}</p>
          {inventory.endpoint_url && <p className="mono" style={{ color: 'var(--faint)', fontSize: 11, marginTop: 4, overflowWrap: 'anywhere' }}>{inventory.endpoint_url}</p>}
          {inventory.last_seen && <p style={{ color: 'var(--faint)', fontSize: 11, marginTop: 4 }}>Last inventoried {new Date(inventory.last_seen).toLocaleString()}</p>}
        </div>
        <span className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>{inventory.transport}</span>
      </div>
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 18, color: 'var(--muted)', fontSize: 13 }}>
        <span>{inventory.tools.length} tools</span>
        <span>Protocol {inventory.protocol_version || 'unspecified'}</span>
        <span>Inventory v{inventory.version}</span>
        <span style={{ color: inventory.integrity_status === 'MODIFIED' ? 'var(--high)' : 'var(--muted)' }}>
          {inventory.integrity_status}
        </span>
      </div>
      <details style={{ marginTop: 14 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--muted)', fontSize: 12 }}>
          Reviewed inventory fingerprint
        </summary>
        <code className="mono" style={{ display: 'block', marginTop: 8, color: 'var(--faint)', fontSize: 11, wordBreak: 'break-all' }}>
          {inventory.inventory_hash}
        </code>
      </details>
      {inventory.instructions && (
        <details style={{ marginTop: 12 }}>
          <summary style={{ cursor: 'pointer', color: 'var(--muted)', fontSize: 12 }}>Server instructions (untrusted)</summary>
          <p style={{ padding: 12, marginTop: 8, background: 'var(--wash)', borderRadius: 8, whiteSpace: 'pre-wrap', fontSize: 13 }}>
            {inventory.instructions}
          </p>
        </details>
      )}
      <Assessment inventory={inventory} />
      {inventory.integrity_status !== 'APPROVED' ? (
        <div style={{ marginTop: 14 }}>
          <button disabled={approving} onClick={() => onApprove(inventory)}>
            {approving ? 'Pinning reviewed snapshot…' : 'Approve and pin this exact fingerprint'}
          </button>
          <p style={{ color: 'var(--faint)', fontSize: 11, marginTop: 6 }}>
            Approval records that an operator reviewed this version; it does not certify the server as safe. Any later change requires review again.
          </p>
        </div>
      ) : <div style={{ marginTop: 14 }}>
        <p className="mono" style={{ color: 'var(--clean)', fontSize: 11 }}>This exact fingerprint is operator-approved.</p>
        <button disabled={approving} onClick={() => onApprove(inventory)} style={{ marginTop: 8 }}>
          {approving ? 'Revoking approval…' : 'Revoke approval'}
        </button>
      </div>}
      <div style={{ marginTop: 20 }}>
        <button onClick={() => setOpen(!open)}>
          {open ? 'Hide tools' : `Review ${inventory.tools.length} tool definitions`}
        </button>
      </div>
      {open && (
        <div style={{ marginTop: 18 }}>
          {inventory.tools.map((tool, index) => <Definition key={`${tool.name}-${index}`} tool={tool} />)}
          {inventory.tools.length === 0 && <p style={{ color: 'var(--muted)' }}>This server currently advertises no tools.</p>}
        </div>
      )}
      {inventory.removed_tools.length > 0 && (
        <div className="hairline" style={{ padding: 14, marginTop: 16 }}>
          <strong style={{ color: 'var(--high)', fontSize: 13 }}>Tools no longer advertised</strong>
          <p className="mono" style={{ color: 'var(--muted)', fontSize: 12, marginTop: 8 }}>
            {inventory.removed_tools.map((tool) => `${tool.name} · v${tool.version}`).join('  /  ')}
          </p>
        </div>
      )}
    </section>
  );
}

export default function Inventory() {
  const [inventories, setInventories] = useState<MCPInventory[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [serverId, setServerId] = useState('');
  const [url, setUrl] = useState('');
  const [token, setToken] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [approvingServer, setApprovingServer] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    fetchInventories()
      .then(setInventories)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Could not load inventories'))
      .finally(() => setLoading(false));
  }, []);

  async function refresh() {
    setRefreshing(true); setError(''); setNotice('');
    try {
      setInventories(await fetchInventories());
      setNotice('Inventory list refreshed from the gateway.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not refresh inventories');
    } finally { setRefreshing(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    setNotice('');
    try {
      const result = await inspectRemoteServer({
        server_id: serverId.trim(), url: url.trim(), ...(token ? { bearer_token: token } : {}),
      });
      setInventories(await fetchInventories());
      setNotice(`Inventory saved (${result.scan_status}). No tools were called.`);
      setToken('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not inspect MCP server');
    } finally {
      setSubmitting(false);
    }
  }

  async function approveSnapshot(inventory: MCPInventory) {
    const approve = inventory.integrity_status !== 'APPROVED';
    setApprovingServer(inventory.server_id);
    setError('');
    setNotice('');
    try {
      await setInventoryApproval({ server_id: inventory.server_id, inventory_hash: inventory.inventory_hash }, approve);
      setInventories(await fetchInventories());
      setNotice(approve ? `Pinned reviewed snapshot for ${inventory.server_id}.`
                        : `Revoked approval for ${inventory.server_id}. Its tools are unavailable to new runs.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update inventory approval');
    } finally {
      setApprovingServer('');
    }
  }

  return (
    <div>
      <header style={{ padding: '56px 0 28px', maxWidth: 760 }}>
        <span className="eyebrow">MCP Registry</span>
        <h1 style={{ fontSize: 'clamp(32px,4vw,44px)', margin: '14px 0 10px' }}>Tool inventory</h1>
        <p className="sub" style={{ fontSize: 16 }}>
          Review the exact definitions advertised by each inventoried server. Treat descriptions and instructions as untrusted input.
        </p>
      </header>
      <div className="hairline" style={{ padding: 14, marginBottom: 20, color: 'var(--muted)', fontSize: 13 }}>
        This view shows metadata only. A fingerprint detects definition changes; it does not prove the server implementation is safe.
      </div>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap', marginBottom: 18 }}>
        <strong>{inventories.length} server snapshot(s)</strong>
        <span style={{ color: 'var(--muted)', fontSize: 13 }}>
          {inventories.filter((item) => item.integrity_status === 'APPROVED').length} approved ·{' '}
          {inventories.reduce((sum, item) => sum + item.tools.length, 0)} advertised tools
        </span>
        <button onClick={() => void refresh()} disabled={refreshing} style={{ marginLeft: 'auto' }}>
          {refreshing ? 'Refreshing…' : 'Refresh inventories'}
        </button>
      </div>
      <form className="card" onSubmit={submit} style={{ padding: 20, marginBottom: 24, display: 'grid', gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 18 }}>Inventory a remote server</h2>
          <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 6 }}>
            Connects over HTTPS and reads server metadata and tool definitions only. The endpoint must be allowlisted by the operator.
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
          <input required maxLength={200} value={serverId} onChange={(e) => setServerId(e.target.value)} placeholder="Inventory ID" aria-label="Inventory ID" />
          <input required type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://host.example/mcp" aria-label="MCP server URL" />
          <input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Optional MCP bearer token" aria-label="Optional MCP bearer token" />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <button className="btn-primary" disabled={submitting} type="submit">
            {submitting ? 'Reading definitions…' : 'Inventory server'}
          </button>
          <span style={{ color: 'var(--faint)', fontSize: 12 }}>The optional MCP token is sent to the MCP server and not saved.</span>
        </div>
      </form>
      {notice && <p role="status" style={{ color: 'var(--clean)', marginBottom: 16 }}>{notice}</p>}
      {loading && <p style={{ color: 'var(--muted)' }}>Loading saved inventories…</p>}
      {error && <p role="alert" style={{ color: 'var(--crit)' }}>{error}</p>}
      {!loading && !error && inventories.length === 0 && (
        <p style={{ color: 'var(--muted)' }}>No saved inventories yet. Run the MCP inventory command to add a server snapshot.</p>
      )}
      <div style={{ display: 'grid', gap: 16 }}>
        {inventories.map((inventory) => <ServerCard key={inventory.server_id} inventory={inventory}
          approving={approvingServer === inventory.server_id} onApprove={approveSnapshot} />)}
      </div>
    </div>
  );
}
