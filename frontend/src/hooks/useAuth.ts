import { useState, useEffect, useCallback } from 'react';
import { auth as authApi } from '../lib/api';

interface User {
  id: string;
  email: string;
  display_name: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      setLoading(false);
      return;
    }
    authApi.me().then((u) => setUser(u as User)).catch(() => {
      localStorage.removeItem('token');
    }).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const resp = await authApi.login({ email, password }) as { access_token: string };
    localStorage.setItem('token', resp.access_token);
    const u = await authApi.me() as User;
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('apiKey');
    localStorage.removeItem('ka-user-type');
    setUser(null);
  }, []);

  return { user, loading, login, logout };
}
