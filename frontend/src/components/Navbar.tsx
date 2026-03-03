import { Link, useLocation } from 'react-router-dom';

const links = [
  { to: '/', label: 'Arena' },
  { to: '/debates', label: 'Debates' },
  { to: '/theses', label: 'Theses' },
  { to: '/leaderboard', label: 'Leaderboard' },
  { to: '/graph', label: 'Graph' },
  { to: '/how-it-works', label: 'How It Works' },
];

export function Navbar() {
  const { pathname } = useLocation();

  return (
    <nav className="border-b border-arena-border bg-arena-surface sticky top-0 z-50">
      <div className="mx-auto px-10 flex items-center h-14 gap-6">
        <Link to="/" className="font-heading font-medium text-arena-text text-xl">
          Knowledge Arena
        </Link>
        <div className="flex gap-1">
          {links.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                pathname === l.to || (l.to !== '/' && pathname.startsWith(l.to))
                  ? 'bg-[#0D6E6E10] text-arena-blue'
                  : 'text-arena-muted hover:text-arena-text'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
        <div className="flex-1" />
        <Link
          to="/login"
          className="bg-arena-blue text-white rounded-lg px-4 py-2 text-[13px] font-semibold hover:opacity-90 transition"
        >
          Sign In
        </Link>
      </div>
    </nav>
  );
}
