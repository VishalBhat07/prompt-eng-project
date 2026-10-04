import { NavLink, Outlet } from 'react-router-dom';

const LINKS = [
  ['/', 'Home'],
  ['/sessions', 'Sessions'],
  ['/graph', 'Graph'],
  ['/findings', 'Findings'],
  ['/approvals', 'Approvals'],
  ['/benchmark', 'Benchmark'],
  ['/demo', 'Demo'],
];

export default function Shell() {
  return (
    <div style={{ minHeight: '100vh' }}>
      <header style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'var(--bg-1)' }}>
        <nav aria-label="primary" style={{ display: 'flex', gap: 4, padding: '12px 24px', alignItems: 'center' }}>
          <span className="mono" style={{ fontWeight: 800, marginRight: 16, color: 'var(--accent)' }}>
            VeriGraph
          </span>
          {LINKS.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}
              style={({ isActive }) => ({
                padding: '6px 12px', borderRadius: 8, textDecoration: 'none',
                color: isActive ? 'var(--ink)' : 'var(--muted)',
                background: isActive ? 'var(--bg-2)' : 'transparent',
              })}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
        <Outlet />
      </main>
    </div>
  );
}
