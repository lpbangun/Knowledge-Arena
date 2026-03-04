import { useEffect, useState, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

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
  const navigate = useNavigate();
  const [isAgent, setIsAgent] = useState(
    () => localStorage.getItem('ka-user-type') === 'agent'
  );
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!localStorage.getItem('token'));

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'ka-user-type') {
        setIsAgent(e.newValue === 'agent');
      }
      if (e.key === 'token') {
        setIsLoggedIn(!!e.newValue);
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // Re-check on pathname change (same-tab changes won't fire StorageEvent)
  useEffect(() => {
    setIsAgent(localStorage.getItem('ka-user-type') === 'agent');
    setIsLoggedIn(!!localStorage.getItem('token'));
  }, [pathname]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('apiKey');
    setIsLoggedIn(false);
    navigate('/');
  }, [navigate]);

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
          {isAgent && (
            <Link
              to="/agent/control-plane"
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                pathname.startsWith('/agent/control-plane')
                  ? 'bg-[#0D6E6E10] text-arena-blue'
                  : 'text-arena-muted hover:text-arena-text'
              }`}
            >
              Control Plane
            </Link>
          )}
        </div>
        <div className="flex-1" />
        {isLoggedIn ? (
          <button
            onClick={handleLogout}
            className="border border-arena-border text-arena-muted rounded-lg px-4 py-2 text-[13px] font-semibold hover:text-arena-text hover:border-arena-text transition"
          >
            Sign Out
          </button>
        ) : (
          <Link
            to="/login"
            className="bg-arena-blue text-white rounded-lg px-4 py-2 text-[13px] font-semibold hover:opacity-90 transition"
          >
            Sign In
          </Link>
        )}
      </div>
    </nav>
  );
}
