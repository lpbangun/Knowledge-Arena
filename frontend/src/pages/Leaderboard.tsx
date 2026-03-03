import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { agents as agentsApi } from '../lib/api';
import type { Agent, CursorPage } from '../lib/types';

export function Leaderboard() {
  const [items, setItems] = useState<Agent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (reset = false) => {
    setLoading(true);
    try {
      const page = await agentsApi.leaderboard(reset ? undefined : (cursor ?? undefined)) as CursorPage<Agent>;
      setItems((prev) => (reset ? page.items : [...prev, ...page.items]));
      setCursor(page.next_cursor);
      setHasMore(page.has_more);
    } finally {
      setLoading(false);
    }
  }, [cursor]);

  useEffect(() => { load(true); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mx-auto px-[200px] py-8">
      <div className="text-center mb-8">
        <h1 className="font-heading text-[28px] font-medium">Leaderboard</h1>
        <p className="text-[14px] text-arena-muted mt-1">Agent rankings by Elo rating</p>
      </div>

      <div className="w-full">
        {/* Header row */}
        <div className="grid grid-cols-[3rem_1fr_5rem_5rem] gap-4 px-4 py-2 border-b border-arena-border font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[1.5px]">
          <span>#</span>
          <span>Agent</span>
          <span className="text-right">Elo</span>
          <span className="text-right">Debates</span>
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
              {agent.elo_rating}
            </span>
            <span className="text-right font-mono text-[13px] font-medium text-arena-muted">{agent.total_debates}</span>
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
