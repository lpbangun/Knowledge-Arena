interface Auxiliary {
  hypothesis: string;
  status: 'open' | 'challenged' | 'falsified' | 'conceded';
}

interface AgentStructure {
  agent_name: string;
  hard_core: string;
  auxiliaries: Auxiliary[];
  falsification_criteria?: string;
}

interface Props {
  structures: AgentStructure[];
}

const STATUS_ICON: Record<string, string> = {
  open: '',
  challenged: '!',
  falsified: 'X',
  conceded: '~',
};

const STATUS_COLOR: Record<string, string> = {
  open: 'border-arena-green text-arena-green',
  challenged: 'border-arena-orange text-arena-orange',
  falsified: 'border-arena-red text-arena-red',
  conceded: 'border-arena-purple text-arena-purple',
};

export function LakatosMap({ structures }: Props) {
  if (!structures.length) {
    return <p className="text-sm text-arena-muted">No Lakatosian structure declared yet.</p>;
  }

  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-sm text-arena-muted uppercase tracking-wide">Lakatosian Structure</h3>
      {structures.map((s) => (
        <div key={s.agent_name} className="bg-arena-elevated border border-arena-border rounded-lg p-4">
          <h4 className="font-semibold text-sm text-arena-blue mb-2">{s.agent_name}</h4>

          {/* Hard Core */}
          <div className="mb-3">
            <span className="text-xs font-mono text-arena-muted uppercase">Hard Core</span>
            <p className="text-sm mt-1 pl-3 border-l-2 border-arena-blue">{s.hard_core}</p>
          </div>

          {/* Auxiliaries */}
          <div className="space-y-2">
            <span className="text-xs font-mono text-arena-muted uppercase">Protective Belt</span>
            {s.auxiliaries.map((aux, i) => (
              <div
                key={i}
                className={`flex items-start gap-2 pl-3 border-l-2 ${STATUS_COLOR[aux.status] ?? 'border-arena-border'}`}
              >
                <span className="font-mono text-xs mt-0.5 w-4 text-center">
                  {STATUS_ICON[aux.status]}
                </span>
                <p className="text-sm flex-1">{aux.hypothesis}</p>
              </div>
            ))}
          </div>

          {/* Legend */}
          <div className="flex gap-3 mt-3 text-xs text-arena-muted">
            <span className="text-arena-green">Open</span>
            <span className="text-arena-orange">Challenged</span>
            <span className="text-arena-red">Falsified</span>
            <span className="text-arena-purple">Conceded</span>
          </div>
        </div>
      ))}
    </div>
  );
}
