// Legenda das cores das zonas/timeline de regime (audit A1 — pedido do Bruno).
// As cores batem com zoneColor() do MainChart e segmentColor() do RegimeTimeline.

interface LegendItem {
  color: string
  label: string
  hint: string
}

const ITEMS: LegendItem[] = [
  { color: '#2563eb', label: 'Risk-On forte', hint: 'BULL, posição cheia' },
  { color: '#60a5fa', label: 'Risk-On', hint: 'BULL, posição parcial' },
  { color: '#a5879199', label: 'Neutro', hint: 'OUT, fora acima da MA200' },
  { color: '#be4852', label: 'Risk-Off', hint: 'BEAR, abaixo da MA200' },
]

export function RegimeLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 px-1 py-1">
      <span className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
        Zonas
      </span>
      {ITEMS.map((it) => (
        <div key={it.label} className="flex items-center gap-1.5" title={it.hint}>
          <span
            className="inline-block h-2.5 w-3.5 rounded-sm"
            style={{ backgroundColor: it.color }}
          />
          <span className="text-xs text-text-primary">{it.label}</span>
          <span className="font-mono text-[10px] text-text-secondary">
            {it.hint}
          </span>
        </div>
      ))}
    </div>
  )
}
