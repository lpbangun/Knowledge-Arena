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
  const [mobileOpen, setMobileOpen] = useState(false);

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
    setMobileOpen(false);
  }, [pathname]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('apiKey');
    localStorage.removeItem('ka-user-type');
    setIsLoggedIn(false);
    setIsAgent(false);
    navigate('/');
  }, [navigate]);

  const navLinks = [
    ...links,
    ...(isAgent ? [{ to: '/agent/control-plane', label: 'Control Plane' }] : []),
  ];

  return (
    <nav className="border-b border-arena-border bg-arena-surface sticky top-0 z-50">
      <div className="mx-auto px-4 sm:px-10 flex items-center h-14 gap-4 sm:gap-6">
        <Link to="/" className="font-heading font-medium text-arena-text text-xl shrink-0">
          Knowledge Arena
        </Link>

        {/* Hamburger button — mobile only */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="sm:hidden p-1.5 text-arena-muted hover:text-arena-text"
          aria-label="Toggle menu"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {mobileOpen
              ? <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              : <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            }
          </svg>
        </button>

        {/* Desktop nav links */}
        <div className="hidden sm:flex gap-1 overflow-x-auto scrollbar-none">
          {navLinks.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className={`px-3 py-1.5 rounded text-sm transition-colors whitespace-nowrap ${
                pathname === l.to || (l.to !== '/' && pathname.startsWith(l.to))
                  ? 'bg-[#0D6E6E10] text-arena-blue'
                  : 'text-arena-muted hover:text-arena-text'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>

        <div className="flex-1 min-w-0" />
        {isLoggedIn ? (
          <button
            onClick={handleLogout}
            className="shrink-0 whitespace-nowrap border border-arena-border text-arena-muted rounded-lg px-4 py-2 text-[13px] font-semibold hover:text-arena-text hover:border-arena-text transition"
          >
            Sign Out
          </button>
        ) : (
          <Link
            to="/login"
            className="shrink-0 whitespace-nowrap bg-arena-blue text-white rounded-lg px-4 py-2 text-[13px] font-semibold hover:opacity-90 transition"
          >
            Sign In
          </Link>
        )}
      </div>

      {/* Mobile dropdown menu */}
      {mobileOpen && (
        <div className="sm:hidden border-t border-arena-border bg-arena-surface flex flex-col px-4 py-2">
          {navLinks.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className={`px-3 py-2 rounded text-sm transition-colors ${
                pathname === l.to || (l.to !== '/' && pathname.startsWith(l.to))
                  ? 'bg-[#0D6E6E10] text-arena-blue'
                  : 'text-arena-muted hover:text-arena-text'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
