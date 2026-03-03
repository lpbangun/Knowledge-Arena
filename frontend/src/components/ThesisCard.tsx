import { formatDistanceToNow } from 'date-fns';
import type { Thesis } from '../lib/types';

const STATUS_COLORS: Record<string, string> = {
  open: 'bg-arena-green/20 text-arena-green',
  challenged: 'bg-arena-orange/20 text-arena-orange',
  standing: 'bg-arena-blue/20 text-arena-blue',
  resolved: 'bg-arena-muted/20 text-arena-muted',
};

interface Props {
  thesis: Thesis;
}

export function ThesisCard({ thesis }: Props) {
  return (
    <div className="bg-arena-surface border border-arena-border rounded-lg p-4 hover:border-arena-blue/50 transition-colors">
      {/* Status badge + time */}
      <div className="flex items-center gap-2 mb-2">
        <span className={`px-2 py-0.5 rounded text-xs font-mono uppercase ${STATUS_COLORS[thesis.status] ?? STATUS_COLORS.open}`}>
          {thesis.status}
        </span>
        <span className="text-xs text-arena-muted">
          {formatDistanceToNow(new Date(thesis.created_at), { addSuffix: true })}
        </span>
      </div>

      {/* Claim */}
      <p className="text-sm mb-3 leading-relaxed">{thesis.claim}</p>

      {/* Meta */}
      <div className="flex items-center gap-3 text-xs text-arena-muted">
        {thesis.category && (
          <span className="px-1.5 py-0.5 bg-arena-elevated rounded">{thesis.category}</span>
        )}
        {thesis.challenge_type && (
          <span>{thesis.challenge_type}</span>
        )}
      </div>
    </div>
  );
}
