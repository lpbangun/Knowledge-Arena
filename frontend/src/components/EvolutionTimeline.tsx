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
      {/* Metrics — 3-column grid */}
      {metrics && (
        <div className="grid grid-cols-3 gap-4 mb-4 pb-3 border-b border-arena-border">
          <div>
            <span className="text-[12px] text-arena-muted block mb-1">Drift</span>
            <span className="font-mono text-[16px] font-bold text-arena-text">{metrics.position_drift.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-[12px] text-arena-muted block mb-1">Nuance</span>
            <span className="font-mono text-[16px] font-bold text-arena-text">+{metrics.nuance_accumulation}</span>
          </div>
          <div>
            <span className="text-[12px] text-arena-muted block mb-1">Resilience</span>
            <span className="font-mono text-[16px] font-bold text-arena-text">{metrics.resilience_score.toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-[4px] top-0 bottom-0 w-px bg-arena-border" />

        {snapshots.map((snap, i) => (
          <div key={snap.snapshot_id} className="relative pl-8 pb-6">
            {/* Dot */}
            <div className={`absolute left-0 top-1 w-[10px] h-[10px] rounded-full ${
              i === 0 ? 'bg-arena-blue' : 'bg-arena-surface border-2 border-arena-purple'
            }`} />

            {/* Content */}
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-[11px] text-arena-muted">
                  {new Date(snap.created_at).toLocaleDateString()}
                </span>
                <span className="text-arena-muted text-[11px]">
                  {snap.snapshot_type === 'post_debate' ? 'After debate' : 'Before debate'}
                </span>
              </div>

              {/* Diffs */}
              {snap.diff?.map((d, j) => (
                <div key={j} className="mt-1 font-mono text-xs">
                  <span className={`font-bold ${
                    d.type === 'added' ? 'text-arena-green' : d.type === 'removed' ? 'text-arena-red' : 'text-arena-orange'
                  }`}>
                    {d.type === 'added' ? '+' : d.type === 'removed' ? '-' : '~'} {d.field}
                  </span>
                  {d.before && (
                    <div className="text-arena-red/70 pl-2">- {d.before}</div>
                  )}
                  {d.after && (
                    <div className="text-arena-green/70 pl-2">+ {d.after}</div>
                  )}
                  {d.prompted_by && (
                    <div className="text-[11px] text-arena-muted pl-2 italic">Prompted by: {d.prompted_by}</div>
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
