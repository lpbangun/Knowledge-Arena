import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useDebate } from '../hooks/useDebate';
import { useWebSocket } from '../hooks/useWebSocket';
import { debates as debatesApi } from '../lib/api';
import { TurnCard } from '../components/TurnCard';
import { LakatosMap } from '../components/LakatosMap';
import { CommentThread } from '../components/CommentThread';
import type { Turn, Comment } from '../lib/types';

export function DebateView() {
  const { debateId } = useParams<{ debateId: string }>();
  const { debate, turns, loading, error, addTurn } = useDebate(debateId);
  const { connected, on } = useWebSocket(debateId);
  const [comments, setComments] = useState<Comment[]>([]);
  const [showComments, setShowComments] = useState(false);

  // Live turn updates — backend sends partial data, fetch full turn
  useEffect(() => {
    return on('turn_submitted', (data) => {
      const evt = data as { turn_id: string; agent_id: string; round: number; turn_type: string };
      if (debateId) {
        debatesApi.turns(debateId).then((r) => {
          const page = r as { items: Turn[] };
          const full = page.items.find((t) => t.id === evt.turn_id);
          if (full) addTurn(full);
        }).catch(() => {});
      }
    });
  }, [on, addTurn, debateId]);

  // Load comments
  useEffect(() => {
    if (!debateId) return;
    debatesApi.comments(debateId).then((r) => {
      const page = r as { items: Comment[] };
      setComments(page.items);
    }).catch(() => {});
  }, [debateId]);

  if (loading) {
    return <div className="max-w-4xl mx-auto px-4 py-8 text-arena-muted">Loading debate...</div>;
  }

  if (error || !debate) {
    return <div className="max-w-4xl mx-auto px-4 py-8 text-arena-red">{error ?? 'Debate not found'}</div>;
  }

  // Parse Lakatosian structures from phase_0_structure
  const structures = debate.phase_0_structure
    ? Object.entries(debate.phase_0_structure).map(([name, data]) => ({
        agent_name: name,
        hard_core: (data as Record<string, unknown>).hard_core as string ?? '',
        auxiliaries: (((data as Record<string, unknown>).auxiliaries ?? []) as Array<{ hypothesis: string; status: string }>).map((a) => ({
          ...a,
          status: a.status as 'open' | 'challenged' | 'falsified' | 'conceded',
        })),
      }))
    : [];

  // Group turns by round
  const roundGroups = new Map<number, Turn[]>();
  turns.forEach((t) => {
    const arr = roundGroups.get(t.round_number) ?? [];
    arr.push(t);
    roundGroups.set(t.round_number, arr);
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <span className={`px-2 py-0.5 rounded text-xs font-mono ${
            debate.status === 'active' ? 'bg-arena-green/20 text-arena-green'
            : debate.status === 'done' ? 'bg-arena-blue/20 text-arena-blue'
            : 'bg-arena-elevated text-arena-muted'
          }`}>
            {debate.status}
          </span>
          {connected && <span className="w-2 h-2 rounded-full bg-arena-green" title="Live" />}
          <span className="text-xs text-arena-muted font-mono">
            Round {debate.current_round}/{debate.max_rounds}
          </span>
        </div>
        <h1 className="text-xl font-bold">{debate.topic}</h1>
        {debate.description && <p className="text-sm text-arena-muted mt-1">{debate.description}</p>}
      </div>

      {/* Content grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Turns column */}
        <div className="lg:col-span-2 space-y-4">
          {Array.from(roundGroups.entries())
            .sort(([a], [b]) => a - b)
            .map(([round, roundTurns]) => (
              <div key={round}>
                <h3 className="text-xs font-mono text-arena-muted uppercase mb-2">Round {round}</h3>
                <div className="space-y-3">
                  {roundTurns.map((turn) => (
                    <TurnCard key={turn.id} turn={turn} />
                  ))}
                </div>
              </div>
            ))}

          {turns.length === 0 && (
            <p className="text-sm text-arena-muted py-8 text-center">No turns submitted yet. Waiting for agents...</p>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Lakatos structure */}
          {structures.length > 0 && <LakatosMap structures={structures} />}

          {/* Comments toggle */}
          <div>
            <button
              onClick={() => setShowComments(!showComments)}
              className="text-sm text-arena-blue hover:underline"
            >
              {showComments ? 'Hide' : 'Show'} Comments ({comments.length})
            </button>
            {showComments && <CommentThread comments={comments} />}
          </div>

          {/* Convergence signals */}
          {debate.convergence_signals && (
            <div className="bg-arena-elevated border border-arena-purple/30 rounded-lg p-3">
              <h3 className="text-xs font-mono text-arena-purple uppercase mb-2">Convergence Signals</h3>
              <pre className="text-xs text-arena-muted font-mono whitespace-pre-wrap">
                {JSON.stringify(debate.convergence_signals, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
