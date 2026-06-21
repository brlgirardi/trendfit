import type { Signal } from '../../api/types'

function segmentColor(sig: Signal): string {
  if (sig.regime === 'BULL' && sig.fraction >= 0.8) return '#1d4ed8'
  if (sig.regime === 'BULL') return '#93c5fd'
  if (sig.regime === 'BEAR') return '#ef4444'
  return '#fca5a5'
}

interface RegimeTimelineProps {
  signals: Signal[]
}

export function RegimeTimeline({ signals }: RegimeTimelineProps) {
  if (signals.length === 0) return null

  return (
    <div className="flex h-2.5 w-full overflow-hidden rounded-sm">
      {signals.map((s) => (
        <div
          key={s.time}
          style={{ flex: 1, backgroundColor: segmentColor(s) }}
        />
      ))}
    </div>
  )
}
