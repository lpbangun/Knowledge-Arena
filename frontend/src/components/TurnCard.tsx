import type { JSX } from 'react';
import { formatDistanceToNow } from 'date-fns';
import type { Turn, ToulminTag } from '../lib/types';

const TAG_COLORS: Record<string, string> = {
  claim: 'text-arena-blue border-arena-blue',
  data: 'text-arena-green border-arena-green',
  warrant: 'text-arena-purple border-arena-purple',
  backing: 'text-arena-teal border-arena-teal',
  qualifier: 'text-arena-orange border-arena-orange',
  rebuttal: 'text-arena-red border-arena-red',
};

function renderHighlightedContent(content: string, tags: ToulminTag[]) {
  if (!tags.length) return <p className="whitespace-pre-wrap">{content}</p>;

  const sorted = [...tags].sort((a, b) => a.start - b.start);
  const segments: JSX.Element[] = [];
  let lastEnd = 0;

  sorted.forEach((tag, i) => {
    if (tag.start > lastEnd) {
      segments.push(<span key={`gap-${i}`}>{content.slice(lastEnd, tag.start)}</span>);
    }
    const cls = `toulmin-${tag.type}`;
    segments.push(
      <span key={`tag-${i}`} className={cls} title={`${tag.type}: ${tag.label}`}>
        {content.slice(tag.start, tag.end)}
      </span>,
    );
    lastEnd = tag.end;
  });

  if (lastEnd < content.length) {
    segments.push(<span key="tail">{content.slice(lastEnd)}</span>);
  }

  return <p className="whitespace-pre-wrap text-sm leading-relaxed">{segments}</p>;
}

interface Props {
  turn: Turn;
  agentName?: string;
  agentElo?: number;
  agentIndex?: number;
}

export function TurnCard({ turn, agentName, agentElo, agentIndex = 0 }: Props) {
  const avatarBg = agentIndex % 2 === 0 ? 'bg-arena-blue' : 'bg-arena-secondary';

  return (
    <div className="bg-arena-surface border border-arena-border rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-9 h-9 rounded-full ${avatarBg} flex items-center justify-center font-mono text-[13px] text-white`}>
          {(agentName ?? turn.agent_id.slice(0, 2)).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <span className="font-semibold text-[14px] text-arena-text truncate block">{agentName ?? turn.agent_id.slice(0, 8)}</span>
          <span className="font-mono text-[11px] font-medium text-arena-muted">
            {agentElo !== undefined ? `Elo ${agentElo} · ` : ''}Round {turn.round_number} · {formatDistanceToNow(new Date(turn.created_at), { addSuffix: true })}
          </span>
        </div>
        {turn.validation_status === 'valid' && (
          <span className="bg-[#2D8A4E15] rounded px-2 py-0.5 font-mono text-[10px] text-arena-green">
            &#10003; Valid
          </span>
        )}
        {turn.validation_status === 'rejected' && (
          <span className="bg-arena-red/15 rounded px-2 py-0.5 font-mono text-[10px] text-arena-red">
            &#10007; Rejected
          </span>
        )}
        {turn.validation_status === 'pending' && (
          <span className="bg-arena-elevated rounded px-2 py-0.5 font-mono text-[10px] text-arena-muted">
            Pending
          </span>
        )}
      </div>

      {/* Content with Toulmin highlighting */}
      <div className="mb-3 text-[#444444] text-[14px] leading-[1.6]">
        {renderHighlightedContent(turn.content, turn.toulmin_tags)}
      </div>

      {/* Tags summary */}
      {turn.toulmin_tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {turn.toulmin_tags.map((tag, i) => (
            <span
              key={i}
              className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${TAG_COLORS[tag.type] ?? 'border-arena-border text-arena-muted'}`}
            >
              {tag.type}
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
