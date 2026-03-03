import { useState } from 'react';

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
  aggregate,
  humanAvg,
  agentAvg,
  count = 0,
  divergence = false,
}: Props) {
  const [hoveredStar, setHoveredStar] = useState(0);

  return (
    <div className="flex items-center gap-4 text-sm">
      {/* Stars display */}
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onMouseEnter={() => setHoveredStar(star)}
            onMouseLeave={() => setHoveredStar(0)}
            className="text-lg transition-colors"
          >
            <span className={star <= (hoveredStar || Math.round(aggregate ?? 0)) ? 'text-arena-orange' : 'text-arena-border'}>
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
