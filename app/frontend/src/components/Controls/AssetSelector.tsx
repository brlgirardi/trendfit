import { ChevronDown } from 'lucide-react'

interface AssetSelectorProps {
  assets: string[]
  selected: string
  onChange: (asset: string) => void
}

export function AssetSelector({ assets, selected, onChange }: AssetSelectorProps) {
  return (
    <div className="relative inline-flex items-center">
      {/* Rotulo discreto reforca qual ativo esta em foco no cockpit. */}
      <span className="pointer-events-none absolute left-3 font-mono text-[10px] uppercase tracking-wide text-text-secondary">
        ativo
      </span>
      <select
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none rounded-lg border border-bull/60 bg-bg-panel py-2 pl-12 pr-9 font-mono text-sm font-semibold text-bull shadow-[0_0_0_1px_rgba(0,255,136,0.12)] outline-none transition-colors hover:border-bull focus:border-bull"
        aria-label="Selecionar ativo"
      >
        {assets.map((a) => (
          <option key={a} value={a} className="bg-bg-panel font-normal text-text-primary">
            {a}
          </option>
        ))}
      </select>
      <ChevronDown
        size={16}
        className="pointer-events-none absolute right-3 text-bull"
      />
    </div>
  )
}
