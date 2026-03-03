import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'register') {
        await fetch('/api/v1/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, display_name: displayName }),
        });
      }
      await login(email, password);
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto px-4 py-16">
      <h1 className="text-xl font-bold text-center mb-8">
        {mode === 'login' ? 'Sign In' : 'Create Account'}
      </h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === 'register' && (
          <div>
            <label className="block text-xs text-arena-muted mb-1">Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded text-sm focus:border-arena-blue focus:outline-none"
              required
            />
          </div>
        )}
        <div>
          <label className="block text-xs text-arena-muted mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded text-sm focus:border-arena-blue focus:outline-none"
            required
          />
        </div>
        <div>
          <label className="block text-xs text-arena-muted mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded text-sm focus:border-arena-blue focus:outline-none"
            required
          />
        </div>

        {error && <p className="text-sm text-arena-red">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 bg-arena-blue text-arena-bg rounded font-medium hover:opacity-90 transition disabled:opacity-50"
        >
          {loading ? 'Loading...' : mode === 'login' ? 'Sign In' : 'Register'}
        </button>
      </form>

      <p className="text-center text-sm text-arena-muted mt-4">
        {mode === 'login' ? (
          <>No account? <button onClick={() => setMode('register')} className="text-arena-blue hover:underline">Register</button></>
        ) : (
          <>Have an account? <button onClick={() => setMode('login')} className="text-arena-blue hover:underline">Sign In</button></>
        )}
      </p>
    </div>
  );
}
