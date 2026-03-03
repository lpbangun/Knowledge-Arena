import { useEffect, useState } from 'react';
import { graph as graphApi } from '../lib/api';
import { GraphViewer } from '../components/GraphViewer';
import type { GraphNode, GraphEdge, CursorPage } from '../lib/types';

export function KnowledgeGraph() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [convergence, setConvergence] = useState<{ index: number; total_nodes: number; total_edges: number } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      graphApi.nodes().then((r) => setNodes((r as CursorPage<GraphNode>).items)),
      graphApi.edges().then((r) => setEdges((r as CursorPage<GraphEdge>).items)),
      graphApi.convergence().then((r) => setConvergence(r as never)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-arena-muted">Loading knowledge graph...</div>;

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-arena-border bg-arena-surface">
        <h1 className="text-sm font-bold">Knowledge Graph</h1>
        <div className="flex gap-4 text-xs font-mono text-arena-muted">
          <span>{nodes.length} nodes</span>
          <span>{edges.length} edges</span>
          {convergence && (
            <span className="text-arena-purple">Convergence: {(convergence.index * 100).toFixed(1)}%</span>
          )}
        </div>
      </div>

      {/* Graph */}
      {nodes.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-arena-muted">
          <p>No knowledge graph data yet. Complete some debates to populate the graph.</p>
        </div>
      ) : (
        <div className="flex-1">
          <GraphViewer nodes={nodes} edges={edges} />
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-4 px-4 py-2 border-t border-arena-border bg-arena-surface text-xs">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-arena-blue" /> Hard Core</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-arena-purple" /> Auxiliary</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-arena-green" /> Evidence</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-arena-orange" /> Open Question</span>
      </div>
    </div>
  );
}
