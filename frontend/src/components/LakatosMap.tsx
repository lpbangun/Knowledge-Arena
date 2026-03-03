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
  challenged: 'border-arena-secondary text-arena-secondary',
  falsified: 'border-arena-red text-arena-red',
  conceded: 'border-arena-purple text-arena-purple',
};

export function LakatosMap({ structures }: Props) {
  if (!structures.length) {
    return <p className="text-sm text-arena-muted">No Lakatosian structure declared yet.</p>;
  }

  return (
    <div className="bg-arena-surface border border-arena-border rounded-xl p-4">
      <h3 className="font-mono text-[11px] font-semibold text-arena-muted uppercase tracking-[2px] mb-4">Lakatos Map</h3>
      <div className="space-y-4">
        {structures.map((s) => (
          <div key={s.agent_name}>
            <h4 className="font-semibold text-[13px] text-arena-blue mb-2">{s.agent_name}</h4>

            {/* Hard Core */}
            <div className="mb-3">
              <span className="font-mono text-[9px] font-semibold text-arena-muted uppercase tracking-[1.5px]">Hard Core</span>
              <p className="text-[12px] leading-[1.4] mt-1 pl-3 border-l-2 border-arena-blue py-1.5">{s.hard_core}</p>
            </div>

            {/* Auxiliaries */}
            <div className="space-y-2">
              <span className="font-mono text-[9px] font-semibold text-arena-muted uppercase tracking-[1.5px]">Protective Belt</span>
              {s.auxiliaries.map((aux, i) => (
                <div
                  key={i}
                  className={`flex items-start gap-2 pl-3 border-l-2 py-1.5 ${STATUS_COLOR[aux.status] ?? 'border-arena-border'}`}
                >
                  <span className="font-mono text-xs mt-0.5 w-4 text-center">
                    {STATUS_ICON[aux.status]}
                  </span>
                  <p className="text-[12px] leading-[1.4] flex-1">{aux.hypothesis}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
