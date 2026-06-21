export type SystemId = 'trendfit' | 'glassnode'

interface SystemSelectorProps {
  selected: SystemId
  onChange: (system: SystemId) => void
}

export function SystemSelector({ selected, onChange }: SystemSelectorProps) {
  const isTrendfit = selected === 'trendfit'

  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-border-line bg-bg-panel p-1">
      <button
        type="button"
        onClick={() => onChange('trendfit')}
        className={`rounded-md px-3 py-1.5 text-sm font-semibold transition-colors ${
          isTrendfit
            ? 'bg-bull text-black'
            : 'bg-transparent text-text-secondary hover:text-text-primary'
        }`}
      >
        TrendFit
      </button>

      <button
        type="button"
        disabled
        title="Em breve"
        className="inline-flex cursor-not-allowed items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold text-text-secondary opacity-50"
      >
        Glassnode
        <span className="rounded-full border border-border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-text-secondary">
          coming soon
        </span>
      </button>
    </div>
  )
}
