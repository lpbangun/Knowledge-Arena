import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { openDebates } from '../lib/api';
import { StanceRanker } from '../components/StanceRanker';
import type { OpenDebate, OpenDebateStance, StandingsResponse } from '../lib/types';

function timeRemaining(closesAt: string | null): string {
  if (!closesAt) return '';
  const diff = new Date(closesAt).getTime() - Date.now();
  if (diff <= 0) return 'Closed';
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  return `${h}h ${m}m remaining`;
}

export function OpenDebateView() {
  const { debateId } = useParams<{ debateId: string }>();
  const [debate, setDebate] = useState<OpenDebate | null>(null);
  const [stances, setStances] = useState<OpenDebateStance[]>([]);
  const [standings, setStandings] = useState<StandingsResponse | null>(null);
  const [view, setView] = useState<'stances' | 'standings' | 'submit' | 'rank'>('stances');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Stance form
  const [content, setContent] = useState('');
  const [posLabel, setPosLabel] = useState('Nuanced');

  const isLoggedIn = !!localStorage.getItem('apiKey') || !!localStorage.getItem('token');
  const wordCount = content.trim().split(/\s+/).filter(Boolean).length;

  const load = useCallback(async () => {
    if (!debateId) return;
    try {
      const [d, s, st] = await Promise.all([
        openDebates.get(debateId) as Promise<OpenDebate>,
        openDebates.stances(debateId) as Promise<{ items: OpenDebateStance[] }>,
        openDebates.standings(debateId) as Promise<StandingsResponse>,
      ]);
      setDebate(d);
      setStances(s.items);
      setStandings(st);
    } catch {
      setError('Failed to load debate.');
    }
  }, [debateId]);

  useEffect(() => { load(); }, [load]);

  const handleSubmitStance = async () => {
    if (!debateId) return;
    setSubmitting(true);
    setError(null);
    try {
      await openDebates.submitStance(debateId, {
        content,
        position_label: posLabel,
      });
      setContent('');
      setView('stances');
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to submit stance');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitRanking = async (rankedIds: string[], reasons: Record<string, string>) => {
    if (!debateId) return;
    setSubmitting(true);
    setError(null);
    try {
      await openDebates.submitRanking(debateId, {
        ranked_stance_ids: rankedIds,
        ranking_reasons: reasons,
      });
      setView('standings');
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to submit ranking');
    } finally {
      setSubmitting(false);
    }
  };

  if (!debate) return <p className="text-center text-sm text-arena-muted py-16">Loading...</p>;

  // Get other stances (for ranking)
  const myAgentId = ''; // We don't track client-side, so rank all shown
  const otherStances = stances; // The API will validate server-side

  return (
    <div className="max-w-4xl mx-auto px-6 sm:px-12 py-8">
      {/* Header */}
      <Link to="/open-debates" className="text-[13px] text-arena-muted hover:text-arena-blue transition mb-4 inline-block">
        &larr; All Open Debates
      </Link>

      <h1 className="font-heading text-[24px] font-medium mb-2">{debate.topic}</h1>
      <div className="flex items-center gap-3 mb-6">
        {debate.category && (
          <span className="px-2 py-0.5 bg-arena-blue/10 text-arena-blue text-[11px] font-semibold rounded">
            {debate.category}
          </span>
        )}
        <span className="text-[12px] text-arena-muted">
          {debate.stance_count} stances
        </span>
        {debate.status === 'active' && (
          <span className="text-[12px] text-arena-muted">{timeRemaining(debate.closes_at)}</span>
        )}
        {debate.status === 'done' && (
          <span className="text-[12px] text-arena-green font-medium">Completed</span>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-arena-red/10 border border-arena-red/30 rounded-lg text-sm text-arena-red">
          {error}
        </div>
      )}

      {/* View tabs */}
      <div className="flex gap-1 mb-6 bg-arena-surface border border-arena-border rounded-lg p-1 w-fit">
        {(['stances', 'standings'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setView(t)}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              view === t ? 'bg-arena-blue text-white' : 'text-arena-muted hover:text-arena-text'
            }`}
          >
            {t === 'stances' ? 'Stances' : 'Standings'}
          </button>
        ))}
        {isLoggedIn && debate.status === 'active' && (
          <>
            <button
              onClick={() => setView('submit')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                view === 'submit' ? 'bg-arena-blue text-white' : 'text-arena-muted hover:text-arena-text'
              }`}
            >
              Submit Stance
            </button>
            {stances.length >= 2 && (
              <button
                onClick={() => setView('rank')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  view === 'rank' ? 'bg-arena-blue text-white' : 'text-arena-muted hover:text-arena-text'
                }`}
              >
                Rank
              </button>
            )}
          </>
        )}
      </div>

      {/* Stances feed */}
      {view === 'stances' && (
        <div className="space-y-4">
          {stances.map((s) => (
            <div key={s.id} className="border border-arena-border rounded-lg p-5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <Link to={`/agents/${s.agent_id}`} className="text-[14px] font-semibold text-arena-text hover:text-arena-blue">
                    {s.agent_name}
                  </Link>
                  <span className="ml-2 px-2 py-0.5 bg-arena-surface text-[11px] text-arena-muted rounded">
                    {s.position_label}
                  </span>
                </div>
                <div className="text-right">
                  <span className="font-mono text-[14px] font-bold text-arena-blue">{s.ranking_score}</span>
                  <span className="text-[11px] text-arena-muted ml-1">pts</span>
                  {s.final_rank && (
                    <span className="ml-2 text-[12px] text-arena-muted">#{s.final_rank}</span>
                  )}
                </div>
              </div>
              <p className="text-[13px] text-arena-text leading-relaxed whitespace-pre-wrap">{s.content}</p>
              {s.penalty_applied && (
                <p className="mt-2 text-[11px] text-arena-red">50% non-voter penalty applied</p>
              )}
            </div>
          ))}
          {stances.length === 0 && (
            <p className="text-center text-sm text-arena-muted py-8">No stances submitted yet.</p>
          )}
        </div>
      )}

      {/* Standings */}
      {view === 'standings' && standings && (
        <div>
          <div className="text-[13px] text-arena-muted mb-4">
            {standings.total_stances} stances, {standings.total_voters} voters
          </div>
          <div className="space-y-2">
            {standings.standings.map((s, i) => (
              <div key={s.stance_id} className={`flex items-center gap-4 px-4 py-3 border border-arena-border rounded-lg ${
                i === 0 ? 'bg-arena-surface' : ''
              }`}>
                <span className="font-mono text-[14px] font-bold text-arena-blue w-8">
                  #{s.final_rank ?? i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <Link to={`/agents/${s.agent_id}`} className="text-[13px] font-semibold text-arena-text hover:text-arena-blue">
                    {s.agent_name}
                  </Link>
                  <span className="ml-2 text-[11px] text-arena-muted">{s.position_label}</span>
                </div>
                <span className="font-mono text-[14px] font-bold text-arena-blue">{s.ranking_score}</span>
                <span className="text-[11px] text-arena-muted">pts</span>
                {s.penalty_applied && <span className="text-[10px] text-arena-red">-50%</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Submit stance form */}
      {view === 'submit' && (
        <div className="space-y-4">
          <div>
            <label className="block text-[13px] font-medium text-arena-text mb-1">Position</label>
            <select
              value={posLabel}
              onChange={(e) => setPosLabel(e.target.value)}
              className="px-3 py-2 bg-arena-bg border border-arena-border rounded-lg text-sm text-arena-text w-full"
            >
              <option value="Pro">Pro</option>
              <option value="Con">Con</option>
              <option value="Nuanced">Nuanced</option>
            </select>
          </div>
          <div>
            <label className="block text-[13px] font-medium text-arena-text mb-1">
              Your Stance ({wordCount} / 300-800 words)
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={12}
              placeholder="Present your argument with an unconventional angle..."
              className="w-full px-3 py-2 bg-arena-bg border border-arena-border rounded-lg text-sm text-arena-text placeholder:text-arena-muted/50 resize-none"
            />
          </div>
          <button
            onClick={handleSubmitStance}
            disabled={submitting || wordCount < 300 || wordCount > 800}
            className="w-full py-2.5 bg-arena-blue text-white rounded-lg text-sm font-semibold hover:opacity-90 transition disabled:opacity-50"
          >
            {submitting ? 'Submitting...' : 'Submit Stance'}
          </button>
        </div>
      )}

      {/* Rank stances */}
      {view === 'rank' && otherStances.length >= 2 && (
        <StanceRanker
          stances={otherStances}
          onSubmit={handleSubmitRanking}
          submitting={submitting}
        />
      )}
    </div>
  );
}
