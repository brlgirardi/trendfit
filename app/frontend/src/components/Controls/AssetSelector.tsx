import { ChevronDown } from 'lucide-react'

interface AssetSelectorProps {
  assets: string[]
  selected: string
  onChange: (asset: string) => void
}

export function AssetSelector({ assets, selected, onChange }: AssetSelectorProps) {
  return (
    <div className="relative inline-flex items-center">
      <select
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none rounded-lg border border-border-line bg-bg-panel py-2 pl-3 pr-9 font-mono text-sm text-text-primary outline-none transition-colors hover:border-text-secondary focus:border-bull"
        aria-label="Selecionar ativo"
      >
        {assets.map((a) => (
          <option key={a} value={a}>
            {a}
          </option>
        ))}
      </select>
      <ChevronDown
        size={16}
        className="pointer-events-none absolute right-3 text-text-secondary"
      />
    </div>
  )
}
