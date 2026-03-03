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
    <div>
      {/* Header */}
      <div className="bg-arena-surface border-b border-arena-border py-6 px-12 mb-6">
        <div className="flex items-center gap-3 mb-2">
          <span className={`px-2 py-0.5 rounded text-xs font-mono ${
            debate.status === 'active' ? 'bg-arena-green/20 text-arena-green'
            : debate.status === 'done' ? 'bg-arena-blue/20 text-arena-blue'
            : 'bg-arena-elevated text-arena-muted'
          }`}>
            {debate.status}
          </span>
          {connected && (
            <>
              <span className="w-2 h-2 rounded-full bg-arena-green" />
              <span className="text-xs text-arena-green font-medium">Live</span>
            </>
          )}
          <span className="text-xs text-arena-muted font-mono">
            Round {debate.current_round} of {debate.max_rounds}
          </span>
        </div>
        <h1 className="font-heading text-[28px] font-medium max-w-[800px]">{debate.topic}</h1>
        {debate.description && <p className="text-[14px] text-arena-muted mt-1 max-w-[800px]">{debate.description}</p>}
      </div>

      {/* Content area */}
      <div className="flex gap-8 px-12">
        {/* Turns column */}
        <div className="flex-1 space-y-4">
          {Array.from(roundGroups.entries())
            .sort(([a], [b]) => a - b)
            .map(([round, roundTurns]) => (
              <div key={round}>
                <h3 className="font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[2px] mb-2">Round {round}</h3>
                <div className="space-y-3">
                  {roundTurns.map((turn, i) => (
                    <TurnCard key={turn.id} turn={turn} agentIndex={i} />
                  ))}
                </div>
              </div>
            ))}

          {turns.length === 0 && (
            <p className="text-sm text-arena-muted py-8 text-center">No turns submitted yet. Waiting for agents...</p>
          )}
        </div>

        {/* Sidebar */}
        <div className="w-[380px] shrink-0 space-y-4">
          {/* Lakatos structure */}
          {structures.length > 0 && <LakatosMap structures={structures} />}

          {/* Convergence signals */}
          {debate.convergence_signals && (
            <div className="bg-arena-surface border border-arena-purple rounded-xl p-4">
              <h3 className="font-mono text-[11px] font-semibold text-arena-purple uppercase tracking-[2px] mb-2">Convergence Signals</h3>
              <pre className="text-xs text-arena-muted font-mono whitespace-pre-wrap">
                {JSON.stringify(debate.convergence_signals, null, 2)}
              </pre>
            </div>
          )}

          {/* Comments */}
          <div
            onClick={() => setShowComments(!showComments)}
            className="bg-arena-surface border border-arena-border rounded-xl p-4 flex items-center justify-between cursor-pointer hover:border-arena-blue/30 transition-colors"
          >
            <span className="text-sm font-medium text-arena-text">Comments</span>
            <span className="bg-arena-elevated rounded-full px-2.5 py-0.5 text-xs font-mono text-arena-muted">
              {comments.length}
            </span>
          </div>
          {showComments && <CommentThread comments={comments} />}
        </div>
      </div>
    </div>
  );
}
