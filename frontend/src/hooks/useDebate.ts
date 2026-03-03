import { useState, useEffect, useCallback } from 'react';
import { debates as debatesApi } from '../lib/api';
import type { Debate, Turn, CursorPage } from '../lib/types';

export function useDebate(debateId: string | undefined) {
  const [debate, setDebate] = useState<Debate | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!debateId) return;
    try {
      setLoading(true);
      const [d, t] = await Promise.all([
        debatesApi.get(debateId) as Promise<Debate>,
        debatesApi.turns(debateId) as Promise<CursorPage<Turn>>,
      ]);
      setDebate(d);
      setTurns(t.items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load debate');
    } finally {
      setLoading(false);
    }
  }, [debateId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const addTurn = useCallback((turn: Turn) => {
    setTurns((prev) => [...prev, turn]);
  }, []);

  return { debate, turns, loading, error, refresh, addTurn };
}
