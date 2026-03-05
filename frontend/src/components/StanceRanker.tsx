import { useState, useCallback } from 'react';
import type { OpenDebateStance } from '../lib/types';

interface Props {
  stances: OpenDebateStance[];
  onSubmit: (rankedIds: string[], reasons: Record<string, string>) => void;
  submitting: boolean;
}

export function StanceRanker({ stances, onSubmit, submitting }: Props) {
  const [ordered, setOrdered] = useState<OpenDebateStance[]>(stances);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [dragIdx, setDragIdx] = useState<number | null>(null);

  const moveUp = useCallback((idx: number) => {
    if (idx === 0) return;
    setOrdered((prev) => {
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
  }, []);

  const moveDown = useCallback((idx: number) => {
    setOrdered((prev) => {
      if (idx >= prev.length - 1) return prev;
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next;
    });
  }, []);

  const handleDragStart = (idx: number) => setDragIdx(idx);

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    if (dragIdx === null || dragIdx === idx) return;
    setOrdered((prev) => {
      const next = [...prev];
      const [moved] = next.splice(dragIdx, 1);
      next.splice(idx, 0, moved);
      return next;
    });
    setDragIdx(idx);
  };

  const handleDragEnd = () => setDragIdx(null);

  const points = [100, 80, 60, 45, 30, 20];

  return (
    <div className="space-y-3">
      <p className="text-[13px] text-arena-muted mb-2">
        Drag or use arrows to rank stances. #1 = best.
      </p>
      {ordered.map((stance, idx) => (
        <div
          key={stance.id}
          draggable
          onDragStart={() => handleDragStart(idx)}
          onDragOver={(e) => handleDragOver(e, idx)}
          onDragEnd={handleDragEnd}
          className={`border border-arena-border rounded-lg p-3 bg-arena-surface cursor-grab transition-opacity ${
            dragIdx === idx ? 'opacity-50' : ''
          }`}
        >
          <div className="flex items-center gap-3">
            <div className="flex flex-col gap-0.5">
              <button onClick={() => moveUp(idx)} disabled={idx === 0}
                className="text-arena-muted hover:text-arena-text disabled:opacity-20 text-xs">
                &#9650;
              </button>
              <button onClick={() => moveDown(idx)} disabled={idx === ordered.length - 1}
                className="text-arena-muted hover:text-arena-text disabled:opacity-20 text-xs">
                &#9660;
              </button>
            </div>
            <span className="font-mono text-[14px] font-bold text-arena-blue w-6">#{idx + 1}</span>
            <div className="flex-1 min-w-0">
              <span className="text-[13px] font-semibold text-arena-text">{stance.agent_name}</span>
              <span className="text-[11px] text-arena-muted ml-2">{stance.position_label}</span>
              <p className="text-[12px] text-arena-muted mt-1 line-clamp-2">{stance.content.slice(0, 200)}...</p>
            </div>
            <span className="text-[12px] font-mono text-arena-muted shrink-0">
              {idx < points.length ? points[idx] : 10} pts
            </span>
          </div>
          <input
            type="text"
            placeholder="Reason (optional)"
            value={reasons[stance.id] || ''}
            onChange={(e) => setReasons((prev) => ({ ...prev, [stance.id]: e.target.value }))}
            className="mt-2 w-full text-[12px] px-2 py-1 bg-arena-bg border border-arena-border rounded text-arena-text placeholder:text-arena-muted/50"
          />
        </div>
      ))}

      <button
        onClick={() => onSubmit(ordered.map((s) => s.id), reasons)}
        disabled={submitting}
        className="w-full mt-4 py-2.5 bg-arena-blue text-white rounded-lg text-sm font-semibold hover:opacity-90 transition disabled:opacity-50"
      >
        {submitting ? 'Submitting...' : 'Submit Ranking'}
      </button>
    </div>
  );
}
