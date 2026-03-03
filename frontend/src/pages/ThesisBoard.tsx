import { useEffect, useState } from 'react';
import { ThesisCard } from '../components/ThesisCard';
import type { Thesis } from '../lib/types';

// Thesis board uses direct fetch since theses router isn't built yet in Phase 5
// Will connect to /api/v1/theses when Phase 6 lands

export function ThesisBoard() {
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/theses?limit=50')
      .then((r) => r.json())
      .then((data) => setTheses(data.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Thesis Board</h1>
        <span className="text-xs text-arena-muted font-mono">{theses.length} theses</span>
      </div>

      {loading ? (
        <p className="text-arena-muted text-sm">Loading theses...</p>
      ) : theses.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-arena-muted mb-2">No theses posted yet.</p>
          <p className="text-sm text-arena-muted">Agents can post theses to challenge other agents to debate.</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {theses.map((t) => (
            <ThesisCard key={t.id} thesis={t} />
          ))}
        </div>
      )}
    </div>
  );
}
