import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { openDebates } from '../lib/api';
import type { OpenDebate } from '../lib/types';

function timeRemaining(closesAt: string | null): string {
  if (!closesAt) return '';
  const diff = new Date(closesAt).getTime() - Date.now();
  if (diff <= 0) return 'Closed';
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  return `${h}h ${m}m remaining`;
}

export function OpenDebates() {
  const [debates, setDebates] = useState<OpenDebate[]>([]);
  const [tab, setTab] = useState<'active' | 'done'>('active');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await openDebates.list(tab) as { items: OpenDebate[] };
      setDebates(data.items);
    } catch {
      setError('Failed to load open debates.');
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="max-w-4xl mx-auto px-6 sm:px-12 py-8">
      <div className="text-center mb-8">
        <h1 className="font-heading text-[28px] font-medium">Open Debates</h1>
        <p className="text-[14px] text-arena-muted mt-1">
          Wildcard-style challenges — submit your stance, rank others, earn points
        </p>
      </div>

      {/* Tab toggle */}
      <div className="flex gap-1 mb-6 bg-arena-surface border border-arena-border rounded-lg p-1 w-fit mx-auto">
        {(['active', 'done'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              tab === t
                ? 'bg-arena-blue text-white'
                : 'text-arena-muted hover:text-arena-text'
            }`}
          >
            {t === 'active' ? 'Active' : 'Completed'}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-arena-red/10 border border-arena-red/30 rounded-lg text-sm text-arena-red">
          {error} <button onClick={load} className="underline">Retry</button>
        </div>
      )}

      {/* Debate cards */}
      <div className="space-y-3">
        {debates.map((d) => (
          <Link
            key={d.id}
            to={`/open-debates/${d.id}`}
            className="block border border-arena-border rounded-lg p-5 hover:bg-arena-surface transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h3 className="text-[15px] font-semibold text-arena-text leading-snug">{d.topic}</h3>
                {d.category && (
                  <span className="inline-block mt-1.5 px-2 py-0.5 bg-arena-blue/10 text-arena-blue text-[11px] font-semibold rounded">
                    {d.category}
                  </span>
                )}
              </div>
              <div className="text-right shrink-0">
                <span className="font-mono text-[14px] font-bold text-arena-blue">{d.stance_count}</span>
                <span className="text-[12px] text-arena-muted ml-1">stances</span>
                {d.status === 'active' && (
                  <p className="text-[11px] text-arena-muted mt-1">{timeRemaining(d.closes_at)}</p>
                )}
                {d.status === 'done' && (
                  <p className="text-[11px] text-arena-green mt-1 font-medium">Completed</p>
                )}
              </div>
            </div>
          </Link>
        ))}

        {debates.length === 0 && !loading && (
          <p className="text-center text-sm text-arena-muted py-8">
            {tab === 'active' ? 'No active open debates right now.' : 'No completed open debates yet.'}
          </p>
        )}
      </div>

      {loading && (
        <p className="text-center text-sm text-arena-muted py-4">Loading...</p>
      )}
    </div>
  );
}
