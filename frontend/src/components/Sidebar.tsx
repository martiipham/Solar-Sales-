import { NavLink } from 'react-router-dom';

interface NavItem {
  path: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: '/dashboard',      label: 'Dashboard',      icon: '⬡' },
  { path: '/calls',          label: 'Calls',          icon: '📞' },
  { path: '/leads',          label: 'Leads',          icon: '⚡' },
  { path: '/emails',         label: 'Email Templates', icon: '✉' },
  { path: '/crm-wizard',     label: 'CRM Wizard',     icon: '🔗' },
  { path: '/knowledge-base', label: 'Knowledge Base', icon: '📖' },
  { path: '/reports',        label: 'Reports',        icon: '📊' },
  { path: '/settings',       label: 'Settings',       icon: '⚙' },
];

const css: Record<string, React.CSSProperties> = {
  sidebar: {
    width: 220,
    minHeight: '100vh',
    backgroundColor: '#0d0d14',
    borderRight: '1px solid #1e1e2e',
    display: 'flex',
    flexDirection: 'column',
    padding: '0 0 16px',
    flexShrink: 0,
  },
  logo: {
    padding: '24px 20px 20px',
    borderBottom: '1px solid #1e1e2e',
    marginBottom: 8,
  },
  logoText: {
    fontSize: 16,
    fontWeight: 700,
    color: '#f0f0f5',
    letterSpacing: '0.05em',
    margin: 0,
  },
  logoSub: {
    fontSize: 11,
    color: '#6b7280',
    margin: '2px 0 0',
  },
  nav: {
    flex: 1,
    padding: '0 8px',
  },
  link: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '9px 12px',
    borderRadius: 6,
    textDecoration: 'none',
    color: '#9ca3af',
    fontSize: 13,
    fontWeight: 500,
    marginBottom: 2,
    transition: 'background-color 0.15s, color 0.15s',
  },
  linkActive: {
    backgroundColor: '#1e1e3a',
    color: '#f0f0f5',
  },
  icon: {
    width: 18,
    textAlign: 'center',
    fontSize: 14,
    flexShrink: 0,
  },
};

export default function Sidebar() {
  return (
    <aside style={css.sidebar}>
      <div style={css.logo}>
        <p style={css.logoText}>SolarAdmin AI</p>
        <p style={css.logoSub}>Voice Receptionist</p>
      </div>
      <nav style={css.nav}>
        {NAV_ITEMS.map(({ path, label, icon }) => (
          <NavLink
            key={path}
            to={path}
            style={({ isActive }) => ({
              ...css.link,
              ...(isActive ? css.linkActive : {}),
            })}
          >
            <span style={css.icon}>{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
