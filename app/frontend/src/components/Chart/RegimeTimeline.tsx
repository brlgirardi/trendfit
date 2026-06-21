import type { Signal } from '../../api/types'

function segmentColor(sig: Signal): string {
  if (sig.regime === 'BULL' && sig.fraction >= 0.8) return '#1d4ed8'
  if (sig.regime === 'BULL') return '#93c5fd'
  if (sig.regime === 'BEAR') return '#ef4444'
  return '#fca5a5'
}

function fmt(ts: number): string {
  return new Date(ts * 1000).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

interface RegimeTimelineProps {
  signals: Signal[]
}

export function RegimeTimeline({ signals }: RegimeTimelineProps) {
  if (signals.length === 0) return null

  // Ticks de início de ano para dar ritmo temporal à faixa (posição proporcional).
  const n = signals.length
  const ticks: { left: number; year: number }[] = []
  let prevYear = -1
  signals.forEach((s, i) => {
    const y = new Date(s.time * 1000).getUTCFullYear()
    if (y !== prevYear) {
      ticks.push({ left: (i / n) * 100, year: y })
      prevYear = y
    }
  })

  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-sm">
        {signals.map((s) => (
          <div
            key={s.time}
            title={`${fmt(s.time)} · ${s.regime}${s.in_position ? ' · comprado' : ''}`}
            style={{ flex: 1, backgroundColor: segmentColor(s) }}
          />
        ))}
      </div>
      {/* Régua de anos: ritmo temporal que a faixa nua não tinha. */}
      <div className="relative mt-0.5 h-3 w-full">
        {ticks.map((t) => (
          <span
            key={t.year}
            className="absolute font-mono text-[8px] text-text-secondary"
            style={{ left: `${t.left}%`, transform: 'translateX(-50%)' }}
          >
            {t.year}
          </span>
        ))}
      </div>
    </div>
  )
}
