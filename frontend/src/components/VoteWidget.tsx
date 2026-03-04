import { useState } from 'react';
import { votes } from '../lib/api';

interface Props {
  targetId: string;
  debateId: string;
  currentScore?: number;
  aggregate?: number | null;
  humanAvg?: number | null;
  agentAvg?: number | null;
  count?: number;
  divergence?: boolean;
}

export function VoteWidget({
  targetId,
  debateId,
  aggregate,
  humanAvg,
  agentAvg,
  count = 0,
  divergence = false,
}: Props) {
  const [hoveredStar, setHoveredStar] = useState(0);
  const [selectedStar, setSelectedStar] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const isLoggedIn = !!localStorage.getItem('token');
  if (!isLoggedIn) {
    return <p className="text-sm text-arena-muted">Sign in to vote</p>;
  }

  const handleVote = async (score: number) => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await votes.cast(debateId, targetId, score);
      setSelectedStar(score);
    } catch {
      // reset on failure
      setSelectedStar(0);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex items-center gap-4 text-sm">
      {/* Stars display */}
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => handleVote(star)}
            onMouseEnter={() => setHoveredStar(star)}
            onMouseLeave={() => setHoveredStar(0)}
            disabled={submitting}
            className="text-lg transition-colors disabled:opacity-50"
          >
            <span className={star <= (hoveredStar || selectedStar || Math.round(aggregate ?? 0)) ? 'text-arena-orange' : 'text-arena-border'}>
              &#9733;
            </span>
          </button>
        ))}
      </div>

      {/* Aggregate */}
      {aggregate !== null && aggregate !== undefined && (
        <span className="font-mono text-arena-text">{aggregate.toFixed(1)}</span>
      )}
      <span className="text-arena-muted">{count} votes</span>

      {/* Breakdown */}
      {humanAvg !== null && humanAvg !== undefined && (
        <span className="text-arena-muted">Human: {humanAvg.toFixed(1)}</span>
      )}
      {agentAvg !== null && agentAvg !== undefined && (
        <span className="text-arena-muted">Agent: {agentAvg.toFixed(1)}</span>
      )}

      {/* Divergence */}
      {divergence && (
        <span className="px-1.5 py-0.5 bg-arena-orange/20 text-arena-orange rounded text-xs font-mono">
          Divergence
        </span>
      )}
    </div>
  );
}
