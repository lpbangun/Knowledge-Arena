import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { debates as debatesApi } from '../lib/api';
import type { Debate, CursorPage } from '../lib/types';

export function DebateArchive() {
  const [items, setItems] = useState<Debate[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('');

  const load = useCallback(async (reset = false) => {
    setLoading(true);
    try {
      const page = await debatesApi.list(
        reset ? undefined : (cursor ?? undefined),
        statusFilter || undefined,
      ) as CursorPage<Debate>;
      setItems((prev) => (reset ? page.items : [...prev, ...page.items]));
      setCursor(page.next_cursor);
      setHasMore(page.has_more);
    } finally {
      setLoading(false);
    }
  }, [cursor, statusFilter]);

  useEffect(() => {
    load(true);
  }, [statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const statuses = ['', 'phase_0', 'active', 'converged', 'done', 'evaluation_failed'];

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-xl font-bold mb-6">Debate Archive</h1>

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {statuses.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
              statusFilter === s ? 'bg-arena-blue text-arena-bg' : 'bg-arena-surface text-arena-muted hover:text-arena-text'
            }`}
          >
            {s || 'All'}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="space-y-2">
        {items.map((d) => (
          <Link key={d.id} to={`/debates/${d.id}`} className="block bg-arena-surface border border-arena-border rounded-lg p-4 hover:border-arena-blue/50 transition-colors">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-sm truncate">{d.topic}</p>
                {d.description && <p className="text-xs text-arena-muted mt-1 line-clamp-2">{d.description}</p>}
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <span className={`px-2 py-0.5 rounded text-xs font-mono ${
                  d.status === 'done' ? 'bg-arena-blue/20 text-arena-blue'
                  : d.status === 'active' ? 'bg-arena-green/20 text-arena-green'
                  : 'bg-arena-elevated text-arena-muted'
                }`}>
                  {d.status}
                </span>
                <span className="text-xs text-arena-muted font-mono">R{d.current_round}/{d.max_rounds}</span>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Load more */}
      {hasMore && (
        <button
          onClick={() => load()}
          disabled={loading}
          className="w-full mt-4 py-2 bg-arena-surface border border-arena-border rounded text-sm text-arena-muted hover:text-arena-text transition-colors"
        >
          {loading ? 'Loading...' : 'Load More'}
        </button>
      )}
    </div>
  );
}
