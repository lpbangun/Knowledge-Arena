import { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import type { GraphNode, GraphEdge } from '../lib/types';

const NODE_COLORS: Record<string, string> = {
  hard_core: '#58A6FF',
  auxiliary: '#BC8CFF',
  empirical_claim: '#3FB950',
  evidence: '#39D2C0',
  synthesis: '#BC8CFF',
  open_question: '#F78166',
};

const EDGE_COLORS: Record<string, string> = {
  SUPPORTS: '#3FB950',
  CONTRADICTS: '#F85149',
  FALSIFIES: '#F85149',
  QUALIFIES: '#F78166',
  EXTENDS: '#58A6FF',
  SYNTHESIZES: '#BC8CFF',
  CHALLENGES: '#F78166',
  EVOLVED_FROM: '#BC8CFF',
};

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export function GraphViewer({ nodes, edges }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...nodes.map((n) => ({
          data: { ...n, id: n.id, label: n.content },
        })),
        ...edges.map((e) => ({
          data: { id: e.id, source: e.source_node_id, target: e.target_node_id, edgeType: e.edge_type, weight: e.strength },
        })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'font-size': '10px',
            color: '#E6EDF3',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'background-color': '#58A6FF',
            width: 24,
            height: 24,
          },
        },
        // Dynamic node colors by type
        ...Object.entries(NODE_COLORS).map(([type, color]) => ({
          selector: `node[node_type="${type}"]`,
          style: { 'background-color': color } as cytoscape.Css.Node,
        })),
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.8,
            width: 1.5,
            'line-color': '#30363D',
            'target-arrow-color': '#30363D',
          } as cytoscape.Css.Edge,
        },
        ...Object.entries(EDGE_COLORS).map(([type, color]) => ({
          selector: `edge[edgeType="${type}"]`,
          style: { 'line-color': color, 'target-arrow-color': color } as cytoscape.Css.Edge,
        })),
      ],
      layout: { name: 'cose', padding: 40 },
    });

    cy.on('tap', 'node', (evt) => {
      const data = evt.target.data() as GraphNode;
      setSelected(data);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) setSelected(null);
    });

    cyRef.current = cy;
    return () => { cy.destroy(); };
  }, [nodes, edges]);

  return (
    <div className="relative w-full h-full min-h-[500px]">
      <div ref={containerRef} className="w-full h-full" />

      {/* Detail panel */}
      {selected && (
        <div className="absolute top-4 right-4 w-72 bg-arena-elevated border border-arena-border rounded-lg p-4 shadow-lg">
          <div className="flex justify-between items-start mb-2">
            <h4 className="font-semibold text-sm">{selected.content}</h4>
            <button onClick={() => setSelected(null)} className="text-arena-muted hover:text-arena-text">
              &times;
            </button>
          </div>
          <p className="text-sm text-arena-muted mb-2">{selected.content}</p>
          <div className="flex gap-2 text-xs font-mono text-arena-muted">
            <span className="px-1 bg-arena-surface rounded">{selected.node_type}</span>
            <span className="px-1 bg-arena-surface rounded">{selected.verification_status}</span>
          </div>
        </div>
      )}
    </div>
  );
}
