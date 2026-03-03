import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { agents as agentsApi } from '../lib/api';
import { EvolutionTimeline } from '../components/EvolutionTimeline';
import type { Agent } from '../lib/types';

interface EloHistory {
  current_elo: number;
  history: Array<{ elo: number; debate_id: string; timestamp: string }>;
}

export function AgentProfile() {
  const { agentId } = useParams<{ agentId: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [eloHistory, setEloHistory] = useState<EloHistory | null>(null);
  const [evolution, setEvolution] = useState<{ snapshots: unknown[]; metrics?: unknown } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!agentId) return;
    Promise.all([
      agentsApi.get(agentId).then((a) => setAgent(a as Agent)),
      agentsApi.eloHistory(agentId).then((h) => setEloHistory(h as EloHistory)),
      agentsApi.evolution(agentId).then((e) => setEvolution(e as { snapshots: unknown[]; metrics?: unknown })).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [agentId]);

  if (loading) return <div className="max-w-4xl mx-auto px-4 py-8 text-arena-muted">Loading...</div>;
  if (!agent) return <div className="max-w-4xl mx-auto px-4 py-8 text-arena-red">Agent not found</div>;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-start gap-4 mb-8">
        <div className="w-16 h-16 rounded-full bg-arena-elevated flex items-center justify-center font-mono text-2xl font-bold text-arena-blue">
          {agent.name.slice(0, 2).toUpperCase()}
        </div>
        <div>
          <h1 className="font-heading text-[28px] font-medium">{agent.name}</h1>
          <div className="flex items-center gap-4 mt-1">
            <span className="font-mono text-[20px] font-bold text-arena-blue">{agent.elo_rating}</span>
            <span className="text-[14px] font-medium text-arena-muted">{agent.total_debates} debates</span>
            {agent.school_of_thought && (
              <span className="bg-[#7C6BAF20] rounded px-2.5 py-0.5 text-[12px] text-arena-purple font-medium">{agent.school_of_thought}</span>
            )}
          </div>
          {agent.model_info && Object.keys(agent.model_info).length > 0 && (
            <span className="font-mono text-[12px] font-medium text-arena-muted mt-1 block">
              {Object.entries(agent.model_info).map(([k, v]) => `${k}: ${v}`).join(' | ')}
            </span>
          )}
        </div>
      </div>

      {/* Elo chart (simple bar) */}
      {eloHistory?.history && eloHistory.history.length > 0 && (
        <div className="mb-8">
          <h2 className="font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[2px] mb-3">Elo History</h2>
          <div className="bg-arena-surface border border-arena-border rounded-xl p-4">
            <div className="flex items-end gap-1 h-32">
              {eloHistory.history.slice(-30).map((h, i, arr) => {
                const min = Math.min(...eloHistory.history.map((x) => x.elo));
                const max = Math.max(...eloHistory.history.map((x) => x.elo));
                const range = max - min || 1;
                const pct = ((h.elo - min) / range) * 100;
                const isLast = i === arr.length - 1;
                return (
                  <div
                    key={i}
                    className={`flex-1 rounded-t transition-colors ${isLast ? 'bg-arena-blue' : 'bg-arena-blue/40'}`}
                    style={{ height: `${Math.max(pct, 5)}%` }}
                    title={`${h.elo} Elo`}
                  />
                );
              })}
            </div>
            <div className="flex justify-between mt-2 text-xs text-arena-muted font-mono">
              <span>{Math.min(...eloHistory.history.map((x) => x.elo))}</span>
              <span>{Math.max(...eloHistory.history.map((x) => x.elo))}</span>
            </div>
          </div>
        </div>
      )}

      {/* Position snapshot */}
      {agent.current_position_snapshot && (
        <div className="mb-8">
          <h2 className="font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[2px] mb-3">Current Position</h2>
          <div className="bg-arena-surface border border-arena-border rounded-xl p-4">
            <p className="text-[14px] leading-[1.6] whitespace-pre-wrap">{agent.current_position_snapshot}</p>
          </div>
        </div>
      )}

      {/* Evolution timeline */}
      {evolution && evolution.snapshots.length > 0 && (
        <div>
          <h2 className="font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[2px] mb-3">Evolution Timeline</h2>
          <div className="bg-arena-surface border border-arena-border rounded-xl p-4">
            <EvolutionTimeline
              snapshots={evolution.snapshots as never[]}
              metrics={evolution.metrics as never}
            />
          </div>
        </div>
      )}
    </div>
  );
}
