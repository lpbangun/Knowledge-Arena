import { Link, useLocation } from 'react-router-dom';

const links = [
  { to: '/', label: 'Arena' },
  { to: '/debates', label: 'Debates' },
  { to: '/theses', label: 'Theses' },
  { to: '/leaderboard', label: 'Leaderboard' },
  { to: '/graph', label: 'Graph' },
];

export function Navbar() {
  const { pathname } = useLocation();

  return (
    <nav className="border-b border-arena-border bg-arena-surface sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 flex items-center h-14 gap-6">
        <Link to="/" className="font-mono font-bold text-arena-blue text-lg tracking-tight">
          KnowledgeArena
        </Link>
        <div className="flex gap-1">
          {links.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                pathname === l.to || (l.to !== '/' && pathname.startsWith(l.to))
                  ? 'bg-arena-elevated text-arena-text'
                  : 'text-arena-muted hover:text-arena-text'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
        <div className="ml-auto">
          <Link
            to="/login"
            className="text-sm text-arena-muted hover:text-arena-text transition-colors"
          >
            Sign In
          </Link>
        </div>
      </div>
    </nav>
  );
}
