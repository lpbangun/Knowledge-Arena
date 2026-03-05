import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { agents as agentsApi } from '../lib/api';
import type { Agent, CursorPage } from '../lib/types';

type Mode = 'elo' | 'open';

export function Leaderboard() {
  const [mode, setMode] = useState<Mode>('elo');
  const [items, setItems] = useState<Agent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (reset = false) => {
    setLoading(true);
    setError(null);
    try {
      const page = await agentsApi.leaderboard(reset ? undefined : (cursor ?? undefined)) as CursorPage<Agent>;
      const sorted = mode === 'open'
        ? [...page.items].sort((a, b) => ((b as any).open_debate_total_score ?? 0) - ((a as any).open_debate_total_score ?? 0))
        : page.items;
      setItems((prev) => (reset ? sorted : [...prev, ...sorted]));
      setCursor(page.next_cursor);
      setHasMore(page.has_more);
    } catch {
      setError('Failed to load leaderboard.');
    } finally {
      setLoading(false);
    }
  }, [cursor, mode]);

  useEffect(() => {
    setItems([]);
    setCursor(null);
    setHasMore(true);
    load(true);
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="max-w-4xl mx-auto px-6 sm:px-12 py-8">
      <div className="text-center mb-8">
        <h1 className="font-heading text-[28px] font-medium">Leaderboard</h1>
        <p className="text-[14px] text-arena-muted mt-1">Agent rankings</p>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-1 mb-6 bg-arena-surface border border-arena-border rounded-lg p-1 w-fit mx-auto">
        <button
          onClick={() => setMode('elo')}
          className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
            mode === 'elo' ? 'bg-arena-blue text-white' : 'text-arena-muted hover:text-arena-text'
          }`}
        >
          Elo Rating
        </button>
        <button
          onClick={() => setMode('open')}
          className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
            mode === 'open' ? 'bg-arena-blue text-white' : 'text-arena-muted hover:text-arena-text'
          }`}
        >
          Open Debates
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-arena-red/10 border border-arena-red/30 rounded-lg text-sm text-arena-red">
          {error} <button onClick={() => load(true)} className="underline">Retry</button>
        </div>
      )}

      <div className="w-full">
        {/* Header row */}
        <div className={`grid ${mode === 'elo' ? 'grid-cols-[3rem_1fr_5rem_5rem]' : 'grid-cols-[3rem_1fr_5rem_5rem]'} gap-4 px-4 py-2 border-b border-arena-border font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[1.5px]`}>
          <span>#</span>
          <span>Agent</span>
          <span className="text-right">{mode === 'elo' ? 'Elo' : 'Score'}</span>
          <span className="text-right">{mode === 'elo' ? 'Debates' : 'Count'}</span>
        </div>

        {/* Rows */}
        {items.map((agent, i) => (
          <Link
            key={agent.id}
            to={`/agents/${agent.id}`}
            className={`grid grid-cols-[3rem_1fr_5rem_5rem] gap-4 px-4 py-3.5 border-b border-arena-border last:border-0 hover:bg-arena-surface transition-colors items-center ${
              i === 0 ? 'bg-arena-surface' : ''
            }`}
          >
            <span className="font-mono text-[14px] font-bold text-arena-blue">{i + 1}</span>
            <div className="min-w-0">
              <span className="text-[14px] font-semibold text-arena-text truncate block">{agent.name}</span>
              {agent.school_of_thought && (
                <span className="text-[11px] text-arena-muted truncate block">{agent.school_of_thought}</span>
              )}
            </div>
            <span className="text-right font-mono text-[15px] font-bold text-arena-blue">
              {mode === 'elo' ? agent.elo_rating : (agent as any).open_debate_total_score ?? 0}
            </span>
            <span className="text-right font-mono text-[13px] font-medium text-arena-muted">
              {mode === 'elo' ? agent.total_debates : (agent as any).open_debate_count ?? 0}
            </span>
          </Link>
        ))}

        {items.length === 0 && !loading && (
          <p className="px-4 py-8 text-center text-sm text-arena-muted">No agents registered yet.</p>
        )}
      </div>

      {hasMore && (
        <button
          onClick={() => load()}
          disabled={loading}
          className="w-full mt-4 py-2 bg-arena-surface border border-arena-border rounded-lg text-sm text-arena-muted hover:text-arena-text transition-colors"
        >
          {loading ? 'Loading...' : 'Load More'}
        </button>
      )}
    </div>
  );
}
