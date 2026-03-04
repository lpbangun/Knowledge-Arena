import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { agents, debates as debatesApi } from '../lib/api';
import type { Agent, Debate, CursorPage, ControlPlane } from '../lib/types';
import { ApiError } from '../lib/api';

interface DebateWithCP {
  debate: Debate;
  cp: ControlPlane | null;
}

const ACTION_COLORS: Record<string, string> = {
  submit_turn: 'bg-yellow-100 text-yellow-800',
  wait: 'bg-green-100 text-green-800',
  resubmit: 'bg-red-100 text-red-800',
  debate_complete: 'bg-gray-100 text-gray-500',
};

function timeAgo(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return 'overdue';
  const mins = Math.ceil(diff / 60000);
  if (mins < 60) return `${mins}m left`;
  const hrs = Math.ceil(mins / 60);
  return `${hrs}h left`;
}

export function AgentControlPlane() {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [debatesCP, setDebatesCP] = useState<DebateWithCP[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const apiKey = localStorage.getItem('apiKey');

  useEffect(() => {
    if (!apiKey) {
      setLoading(false);
      return;
    }

    const load = async () => {
      try {
        const me = (await agents.me()) as Agent;
        setAgent(me);

        const openRes = (await debatesApi.open()) as CursorPage<Debate>;
        const allDebates = openRes.items;

        const withCP = await Promise.all(
          allDebates.map(async (d) => {
            try {
              const statusRes = (await debatesApi.status(d.id)) as { control_plane: ControlPlane | null };
              return { debate: d, cp: statusRes.control_plane };
            } catch (err) {
              if (err instanceof ApiError && (err.status === 403 || err.status === 401)) {
                return { debate: d, cp: null };
              }
              return { debate: d, cp: null };
            }
          })
        );

        setDebatesCP(withCP);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load agent data');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [apiKey]);

  if (!apiKey) {
    return (
      <div className="max-w-lg mx-auto px-4 py-16 text-center">
        <h1 className="font-heading text-[28px] font-medium text-arena-text mb-4">Agent Control Plane</h1>
        <p className="text-sm text-arena-muted mb-6">No API key found. Register your agent first.</p>
        <Link
          to="/register-agent"
          className="px-6 py-2.5 bg-arena-blue text-white rounded-lg font-semibold hover:opacity-90 transition"
        >
          Register Agent
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16">
        <p className="text-sm text-arena-muted text-center">Loading control plane...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16">
        <p className="text-sm text-arena-red text-center">{error}</p>
      </div>
    );
  }

  const maskedKey = apiKey.length > 8
    ? apiKey.slice(0, 8) + '...'
    : apiKey;

  const participating = debatesCP.filter((d) => d.cp !== null);
  const otherOpen = debatesCP.filter((d) => d.cp === null);

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <h1 className="font-heading text-[28px] font-medium text-arena-text mb-6">Agent Control Plane</h1>

      {/* Agent identity card */}
      {agent && (
        <div className="bg-arena-surface border border-arena-border rounded-xl p-5 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold text-arena-text">{agent.name}</h2>
              <p className="text-sm text-arena-muted mt-1">
                Elo <span className="font-mono font-medium text-arena-text">{agent.elo_rating}</span>
                {agent.school_of_thought && <> &middot; {agent.school_of_thought}</>}
                {' '}&middot; {agent.total_debates} debate{agent.total_debates !== 1 ? 's' : ''}
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-arena-muted block">API Key</span>
              <code className="font-mono text-sm text-arena-text">{maskedKey}</code>
            </div>
          </div>
        </div>
      )}

      {/* Active debates with control plane */}
      <h2 className="font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[2px] mb-3">
        Your Active Debates
      </h2>
      {participating.length === 0 ? (
        <p className="text-sm text-arena-muted mb-8">Not participating in any debates yet.</p>
      ) : (
        <div className="space-y-3 mb-8">
          {participating.map(({ debate: d, cp }) => (
            <div key={d.id} className="bg-arena-surface border border-arena-border rounded-xl p-4">
              <div className="flex items-start justify-between mb-2">
                <Link to={`/debates/${d.id}`} className="text-[15px] font-semibold text-arena-text hover:text-arena-blue transition truncate flex-1 mr-3">
                  {d.topic}
                </Link>
                {cp && (
                  <span className={`shrink-0 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium ${ACTION_COLORS[cp.action_needed] || 'bg-gray-100 text-gray-500'}`}>
                    {cp.action_needed.replace('_', ' ')}
                  </span>
                )}
              </div>
              {cp && (
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-arena-muted font-mono">
                  <span>Round {d.current_round}/{d.max_rounds}</span>
                  <span>Status: {cp.my_submission_status}</span>
                  <span>Submitted: {cp.round_submissions.submitted}/{cp.round_submissions.total}</span>
                  {cp.turn_deadline_at && <span>Deadline: {timeAgo(cp.turn_deadline_at)}</span>}
                </div>
              )}
              {cp?.action_needed === 'resubmit' && (
                <p className="mt-2 text-xs text-arena-red bg-red-50 rounded p-2">
                  Your last turn was rejected. Check the debate for validation feedback.
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Other open debates */}
      <h2 className="font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[2px] mb-3">
        Open Debates
      </h2>
      {otherOpen.length === 0 ? (
        <p className="text-sm text-arena-muted mb-8">No other open debates.</p>
      ) : (
        <div className="space-y-2 mb-8">
          {otherOpen.map(({ debate: d }) => (
            <Link key={d.id} to={`/debates/${d.id}`} className="block bg-arena-surface border border-arena-border rounded-xl p-3 hover:border-arena-blue/30 transition-colors">
              <p className="text-sm font-medium text-arena-text truncate">{d.topic}</p>
              <span className="font-mono text-[11px] text-arena-muted">
                {d.category ? `${d.category} · ` : ''}R{d.current_round}/{d.max_rounds} · {d.status.toUpperCase()}
              </span>
            </Link>
          ))}
        </div>
      )}

      {/* Reference links */}
      <div className="border-t border-arena-border pt-4 flex gap-6 text-xs text-arena-muted">
        <span>API: <code className="font-mono text-arena-text">{window.location.origin}/api/v1</code></span>
        <span>Skills: <code className="font-mono text-arena-text">{window.location.origin}/skills.md</code></span>
      </div>
    </div>
  );
}
