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

function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
      <circle cx="4" cy="11" r="2.4" fill="none" stroke="#5eead4" strokeWidth="1.6" />
      <circle cx="11" cy="5.5" r="2.4" fill="none" stroke="rgba(255,255,255,0.55)" strokeWidth="1.6" />
      <circle cx="18" cy="11" r="2.4" fill="#5eead4" opacity="0.9" />
      <circle cx="11" cy="16.5" r="2.4" fill="none" stroke="#ff636f" strokeWidth="1.6" />
      <path d="M6 10 9.2 6.8M12.8 6.8 16 10M6 12l3.2 3.2M12.8 15.2 16 12" stroke="rgba(255,255,255,0.3)" strokeWidth="1.2" />
    </svg>
  );
}

export default function Shell() {
  return (
    <div style={{ minHeight: '100vh' }}>
      <header style={{
        position: 'sticky', top: 0, zIndex: 50,
        backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)',
        background: 'rgba(9,9,12,0.72)', borderBottom: '1px solid var(--line)',
      }}>
        <nav aria-label="primary" style={{
          display: 'flex', alignItems: 'center', gap: 4,
          maxWidth: 1180, margin: '0 auto', padding: '0 24px', height: 60,
        }}>
          <NavLink to="/" style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none', marginRight: 20 }}>
            <Mark />
            <span style={{ fontWeight: 650, fontSize: 15, letterSpacing: '-0.01em' }}>VeriGraph</span>
          </NavLink>
          <div style={{ display: 'flex', gap: 2 }}>
            {LINKS.slice(1).map(([to, label]) => (
              <NavLink key={to} to={to}
                style={({ isActive }) => ({
                  padding: '7px 12px', borderRadius: 7, textDecoration: 'none', fontSize: 14,
                  color: isActive ? 'var(--ink)' : 'var(--muted)',
                  background: isActive ? 'rgba(255,255,255,0.07)' : 'transparent',
                })}>
                {label}
              </NavLink>
            ))}
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--faint)' }}>
            <span style={{ width: 7, height: 7, borderRadius: 999, background: 'var(--clean)', display: 'inline-block' }} />
            <span className="mono">v0.1 · lab</span>
          </div>
        </nav>
      </header>
      <main style={{ maxWidth: 1180, margin: '0 auto', padding: '0 24px 96px' }}>
        <Outlet />
      </main>
    </div>
  );
}
