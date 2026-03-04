import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import type { Thesis } from '../lib/types';

const STATUS_COLORS: Record<string, string> = {
  open: 'bg-[#0D6E6E15] text-arena-blue',
  challenged: 'bg-[#E07B5420] text-arena-secondary',
  standing: 'bg-[#0D6E6E15] text-arena-blue',
  resolved: 'bg-[#88888820] text-arena-muted',
};

interface Props {
  thesis: Thesis;
}

export function ThesisCard({ thesis }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      className="bg-arena-surface border border-arena-border rounded-xl p-5 hover:border-arena-blue/30 transition-colors cursor-pointer"
    >
      {/* Status badge + time */}
      <div className="flex items-center justify-between mb-3">
        <span className={`px-2 py-0.5 rounded text-xs font-mono uppercase ${STATUS_COLORS[thesis.status] ?? STATUS_COLORS.open}`}>
          {thesis.status}
        </span>
        <span className="text-[11px] text-arena-muted font-mono">
          {formatDistanceToNow(new Date(thesis.created_at), { addSuffix: true })}
        </span>
      </div>

      {/* Claim */}
      <p className="text-[14px] font-medium leading-[1.5] text-arena-text mb-3">{thesis.claim}</p>

      {/* Meta */}
      <div className="flex items-center gap-3 text-[11px] text-arena-muted">
        {thesis.category && (
          <span className="px-2.5 py-0.5 bg-arena-elevated rounded">{thesis.category}</span>
        )}
        {thesis.challenge_type && (
          <span>{thesis.challenge_type}</span>
        )}
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-arena-border" onClick={(e) => e.stopPropagation()}>
          {thesis.evidence_summary && (
            <p className="text-[13px] text-arena-muted mb-3 leading-[1.6]">{thesis.evidence_summary}</p>
          )}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 text-[11px] text-arena-muted">
              <span>{thesis.challenger_count} challengers</span>
              <span>{thesis.view_count} views</span>
            </div>
            {thesis.status === 'open' && (
              <button
                className="px-3 py-1 bg-arena-blue text-white rounded text-[12px] font-semibold hover:opacity-90 transition"
                onClick={() => alert(`Challenge thesis: ${thesis.id}`)}
              >
                Challenge
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
