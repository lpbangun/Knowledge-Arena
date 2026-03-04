import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useDebate } from '../hooks/useDebate';
import { useWebSocket } from '../hooks/useWebSocket';
import { debates as debatesApi, agents as agentsApi } from '../lib/api';
import { TurnCard } from '../components/TurnCard';
import { LakatosMap } from '../components/LakatosMap';
import { CommentThread } from '../components/CommentThread';
import { VoteWidget } from '../components/VoteWidget';
import type { Turn, Comment, Evaluation } from '../lib/types';

export function DebateView() {
  const { debateId } = useParams<{ debateId: string }>();
  const { debate, turns, loading, error, addTurn } = useDebate(debateId);
  const { connected, on } = useWebSocket(debateId);
  const [comments, setComments] = useState<Comment[]>([]);
  const [showComments, setShowComments] = useState(false);
  const [agentMap, setAgentMap] = useState<Map<string, { name: string; elo: number }>>(new Map());
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);

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

  // Fetch evaluation for completed debates
  useEffect(() => {
    if (debate?.status === 'done' && debateId) {
      debatesApi.evaluation(debateId).then((r) => setEvaluation(r as Evaluation)).catch(() => {});
    }
  }, [debate?.status, debateId]);

  // Build agent lookup map from turn agent_ids
  useEffect(() => {
    if (!turns.length) return;
    const uniqueIds = [...new Set(turns.map((t) => t.agent_id).filter(Boolean))];
    Promise.all(
      uniqueIds.map((id) =>
        (agentsApi.get(id) as Promise<{ id: string; name: string; elo_score: number }>)
          .then((a) => [id, { name: a.name, elo: a.elo_score }] as const)
          .catch(() => null)
      )
    ).then((results) => {
      const map = new Map<string, { name: string; elo: number }>();
      results.forEach((r) => { if (r) map.set(r[0], r[1]); });
      setAgentMap(map);
    });
  }, [turns]);

  if (loading) {
    return <div className="max-w-4xl mx-auto px-4 py-8 text-arena-muted">Loading debate...</div>;
  }

  if (error || !debate) {
    return <div className="max-w-4xl mx-auto px-4 py-8 text-arena-red">{error ?? 'Debate not found'}</div>;
  }

  const isLoggedIn = !!localStorage.getItem('token');

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
      <div className="bg-arena-surface border-b border-arena-border py-6 px-6 sm:px-12 mb-6">
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
      <div className="flex flex-col lg:flex-row gap-8 px-6 sm:px-12">
        {/* Turns column */}
        <div className="flex-1 min-w-0 space-y-4">
          {Array.from(roundGroups.entries())
            .sort(([a], [b]) => a - b)
            .map(([round, roundTurns]) => (
              <div key={round}>
                <h3 className="font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[2px] mb-2">Round {round}</h3>
                <div className="space-y-3">
                  {roundTurns.map((turn, i) => {
                    const agent = agentMap.get(turn.agent_id);
                    return (
                      <div key={turn.id}>
                        <TurnCard
                          turn={turn}
                          agentIndex={i}
                          agentName={agent?.name}
                          agentElo={agent?.elo}
                        />
                        <div className="mt-2 px-4">
                          {isLoggedIn ? (
                            <VoteWidget
                              targetId={turn.id}
                              debateId={debateId!}
                              aggregate={(turn as unknown as Record<string, number>).vote_aggregate ?? undefined}
                              humanAvg={(turn as unknown as Record<string, number>).human_avg ?? undefined}
                              agentAvg={(turn as unknown as Record<string, number>).agent_avg ?? undefined}
                              count={(turn as unknown as Record<string, number>).vote_count ?? 0}
                              divergence={(turn as unknown as Record<string, boolean>).vote_divergence ?? false}
                            />
                          ) : (
                            <p className="text-sm text-arena-muted">Sign in to vote</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}

          {turns.length === 0 && (
            <p className="text-sm text-arena-muted py-8 text-center">No turns submitted yet. Waiting for agents...</p>
          )}
        </div>

        {/* Sidebar */}
        <div className="w-full lg:w-[380px] shrink-0 space-y-4">
          {/* Lakatos structure */}
          {structures.length > 0 && <LakatosMap structures={structures} />}

          {/* Convergence signals */}
          {debate.convergence_signals && (
            <div className="bg-arena-surface border border-arena-purple rounded-xl p-4">
              <h3 className="font-mono text-[11px] font-semibold text-arena-purple uppercase tracking-[2px] mb-2">Convergence Signals</h3>
              <div className="space-y-2">
                {Object.entries(debate.convergence_signals).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between text-xs">
                    <span className="text-arena-muted capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className={`font-mono px-2 py-0.5 rounded ${
                      value === true ? 'bg-arena-green/15 text-arena-green'
                      : value === false ? 'bg-arena-elevated text-arena-muted'
                      : 'text-arena-text'
                    }`}>
                      {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evaluation results for completed debates */}
          {evaluation && (
            <div className="bg-arena-surface border border-arena-blue rounded-xl p-4">
              <h3 className="font-mono text-[11px] font-semibold text-arena-blue uppercase tracking-[2px] mb-3">Evaluation</h3>
              <div className="space-y-3">
                {evaluation.evaluations.map((ev) => {
                  const agent = agentMap.get(ev.agent_id);
                  return (
                    <div key={ev.agent_id} className="border-b border-arena-border pb-2 last:border-0 last:pb-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-semibold text-arena-text">{agent?.name ?? ev.agent_id.slice(0, 8)}</span>
                        <span className="font-mono text-xs text-arena-blue">{ev.composite_score.toFixed(2)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-arena-muted font-mono">
                        <span>Elo: {ev.elo_before} → {ev.elo_after}</span>
                        <span className={ev.elo_after >= ev.elo_before ? 'text-arena-green' : 'text-arena-red'}>
                          ({ev.elo_after >= ev.elo_before ? '+' : ''}{ev.elo_after - ev.elo_before})
                        </span>
                      </div>
                      {ev.narrative_feedback && (
                        <p className="text-xs text-arena-muted mt-1 line-clamp-2">{ev.narrative_feedback}</p>
                      )}
                    </div>
                  );
                })}
              </div>
              {evaluation.synthesis && (
                <div className="mt-3 pt-3 border-t border-arena-border">
                  <h4 className="font-mono text-[10px] font-semibold text-arena-muted uppercase tracking-[1.5px] mb-2">Synthesis</h4>
                  {evaluation.synthesis.agreements && (
                    <div className="mb-2"><span className="text-xs font-semibold text-arena-green">Agreements:</span><p className="text-xs text-arena-muted">{evaluation.synthesis.agreements}</p></div>
                  )}
                  {evaluation.synthesis.disagreements && (
                    <div className="mb-2"><span className="text-xs font-semibold text-arena-red">Disagreements:</span><p className="text-xs text-arena-muted">{evaluation.synthesis.disagreements}</p></div>
                  )}
                  {evaluation.synthesis.novel_positions && (
                    <div className="mb-2"><span className="text-xs font-semibold text-arena-purple">Novel Positions:</span><p className="text-xs text-arena-muted">{evaluation.synthesis.novel_positions}</p></div>
                  )}
                  {evaluation.synthesis.open_questions && (
                    <div><span className="text-xs font-semibold text-arena-orange">Open Questions:</span><p className="text-xs text-arena-muted">{evaluation.synthesis.open_questions}</p></div>
                  )}
                </div>
              )}
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
          {showComments && (
            <CommentThread
              comments={comments}
              debateId={debateId!}
              onCommentPosted={(comment) => setComments((prev) => [...prev, comment])}
            />
          )}
        </div>
      </div>
    </div>
  );
}
