interface Snapshot {
  snapshot_id: string;
  snapshot_type: string;
  source_debate_id: string;
  created_at: string;
  diff?: DiffEntry[];
}

interface DiffEntry {
  type: 'added' | 'removed' | 'modified';
  field: string;
  before?: string;
  after?: string;
  prompted_by?: string;
}

interface Props {
  snapshots: Snapshot[];
  metrics?: {
    position_drift: number;
    nuance_accumulation: number;
    resilience_score: number;
  };
}

export function EvolutionTimeline({ snapshots, metrics }: Props) {
  return (
    <div>
      {/* Metrics bar */}
      {metrics && (
        <div className="flex gap-6 mb-4 font-mono text-xs text-arena-muted border-b border-arena-border pb-3">
          <span>Drift: {metrics.position_drift.toFixed(2)}</span>
          <span>Nuance: +{metrics.nuance_accumulation}</span>
          <span>Resilience: {metrics.resilience_score.toFixed(2)}</span>
        </div>
      )}

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-3 top-0 bottom-0 w-px bg-arena-border" />

        {snapshots.map((snap, i) => (
          <div key={snap.snapshot_id} className="relative pl-8 pb-6">
            {/* Dot */}
            <div className={`absolute left-1.5 top-1 w-3 h-3 rounded-full border-2 ${
              i === 0 ? 'bg-arena-blue border-arena-blue' : 'bg-arena-surface border-arena-purple'
            }`} />

            {/* Content */}
            <div>
              <div className="flex items-center gap-2 text-sm mb-1">
                <span className="text-arena-text font-medium">
                  {new Date(snap.created_at).toLocaleDateString()}
                </span>
                <span className="text-arena-muted text-xs">
                  {snap.snapshot_type === 'post_debate' ? 'After debate' : 'Before debate'}
                </span>
              </div>

              {/* Diffs */}
              {snap.diff?.map((d, j) => (
                <div key={j} className="mt-1 font-mono text-xs">
                  <span className={`font-bold ${
                    d.type === 'added' ? 'text-arena-green' : d.type === 'removed' ? 'text-arena-red' : 'text-arena-orange'
                  }`}>
                    {d.type.toUpperCase()} {d.field}
                  </span>
                  {d.before && (
                    <div className="text-arena-red/70 pl-2">- {d.before}</div>
                  )}
                  {d.after && (
                    <div className="text-arena-green/70 pl-2">+ {d.after}</div>
                  )}
                  {d.prompted_by && (
                    <div className="text-arena-muted pl-2 italic">Prompted by: {d.prompted_by}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
