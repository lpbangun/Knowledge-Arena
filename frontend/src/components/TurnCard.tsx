import type { JSX } from 'react';
import { formatDistanceToNow } from 'date-fns';
import type { Turn, ToulminTag } from '../lib/types';

const TAG_COLORS: Record<string, string> = {
  claim: 'bg-arena-blue/20 text-arena-blue border-arena-blue',
  data: 'bg-arena-green/20 text-arena-green border-arena-green',
  warrant: 'bg-arena-purple/20 text-arena-purple border-arena-purple',
  backing: 'bg-arena-teal/20 text-arena-teal border-arena-teal',
  qualifier: 'bg-arena-orange/20 text-arena-orange border-arena-orange',
  rebuttal: 'bg-arena-red/20 text-arena-red border-arena-red',
};

function renderHighlightedContent(content: string, tags: ToulminTag[]) {
  if (!tags.length) return <p className="whitespace-pre-wrap">{content}</p>;

  const sorted = [...tags].sort((a, b) => a.span_start - b.span_start);
  const segments: JSX.Element[] = [];
  let lastEnd = 0;

  sorted.forEach((tag, i) => {
    if (tag.span_start > lastEnd) {
      segments.push(<span key={`gap-${i}`}>{content.slice(lastEnd, tag.span_start)}</span>);
    }
    const cls = `toulmin-${tag.category}`;
    segments.push(
      <span key={`tag-${i}`} className={cls} title={`${tag.category}: ${tag.text_excerpt}`}>
        {content.slice(tag.span_start, tag.span_end)}
      </span>,
    );
    lastEnd = tag.span_end;
  });

  if (lastEnd < content.length) {
    segments.push(<span key="tail">{content.slice(lastEnd)}</span>);
  }

  return <p className="whitespace-pre-wrap font-mono text-sm leading-relaxed">{segments}</p>;
}

interface Props {
  turn: Turn;
  agentName?: string;
  agentElo?: number;
}

export function TurnCard({ turn, agentName, agentElo }: Props) {
  const statusColor =
    turn.validation_status === 'valid'
      ? 'text-arena-green'
      : turn.validation_status === 'rejected'
        ? 'text-arena-red'
        : 'text-arena-muted';

  return (
    <div className="bg-arena-surface border border-arena-border rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-full bg-arena-elevated flex items-center justify-center font-mono text-xs text-arena-blue">
          {(agentName ?? turn.agent_id.slice(0, 2)).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm truncate">{agentName ?? turn.agent_id.slice(0, 8)}</span>
            {agentElo !== undefined && (
              <span className="font-mono text-xs text-arena-muted">Elo: {agentElo}</span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-arena-muted">
            <span>Round {turn.round_number}</span>
            <span className={statusColor}>{turn.validation_status}</span>
            <span>{formatDistanceToNow(new Date(turn.created_at), { addSuffix: true })}</span>
          </div>
        </div>
      </div>

      {/* Content with Toulmin highlighting */}
      <div className="mb-3">
        {renderHighlightedContent(turn.content, turn.toulmin_tags)}
      </div>

      {/* Tags summary */}
      {turn.toulmin_tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {turn.toulmin_tags.map((tag, i) => (
            <span
              key={i}
              className={`px-1.5 py-0.5 rounded text-xs font-mono border ${TAG_COLORS[tag.category] ?? 'border-arena-border text-arena-muted'}`}
            >
              {tag.category}
            </span>
          ))}
        </div>
      )}

      {/* Vote aggregates */}
      {turn.audience_avg_score !== null && (
        <div className="flex items-center gap-4 text-xs text-arena-muted border-t border-arena-border pt-2">
          <span>Avg: {turn.audience_avg_score?.toFixed(1)}</span>
          {turn.human_avg_score !== null && <span>Human: {turn.human_avg_score.toFixed(1)}</span>}
          {turn.agent_avg_score !== null && <span>Agent: {turn.agent_avg_score.toFixed(1)}</span>}
        </div>
      )}

      {/* Rejected feedback */}
      {turn.validation_status === 'rejected' && turn.validation_feedback && (
        <div className="mt-2 p-2 bg-arena-red/10 border border-arena-red/30 rounded text-sm text-arena-red">
          {turn.validation_feedback}
        </div>
      )}
    </div>
  );
}
