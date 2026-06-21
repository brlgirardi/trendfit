import type { Signal } from '../api/types'

interface RiskGaugeProps {
  signals: Signal[]
}

interface RiskInfo {
  label: string
  position: number
  color: string
  /** Subtítulo que amarra o nível de risco à leitura da carteira (audit M2). */
  hint: string
}

function getRiskInfo(sig: Signal | null): RiskInfo {
  if (!sig)
    return { label: 'Mild Risk-Off', position: 37.5, color: '#fca5a5', hint: 'fora — aguarda confirmação' }
  if (sig.regime === 'BULL' && sig.fraction >= 0.8)
    return { label: 'Strong Risk-On', position: 87.5, color: '#1d4ed8', hint: 'sistema comprado — posição cheia' }
  if (sig.regime === 'BULL')
    return { label: 'Mild Risk-On', position: 62.5, color: '#93c5fd', hint: 'comprado parcial — exposição reduzida' }
  if (sig.regime === 'BEAR')
    return { label: 'Strong Risk-Off', position: 12.5, color: '#ef4444', hint: 'sistema fora — preserva capital' }
  return { label: 'Mild Risk-Off', position: 37.5, color: '#fca5a5', hint: 'fora — acima da MA200, sem sinal' }
}

function findLastInflection(signals: Signal[]): string | null {
  for (let i = signals.length - 1; i > 0; i--) {
    if (signals[i].regime !== signals[i - 1].regime) {
      const d = new Date(signals[i].time * 1000)
      return d.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
    }
  }
  return null
}

export function RiskGauge({ signals }: RiskGaugeProps) {
  const last = signals.length > 0 ? signals[signals.length - 1] : null
  const risk = getRiskInfo(last)
  const inflectionDate = findLastInflection(signals)

  return (
    <div className="flex h-full flex-col gap-3 rounded-lg border border-border-line bg-bg-panel px-4 py-4">
      <div className="font-mono text-[9px] tracking-widest text-text-secondary">
        RISK GAUGE
      </div>

      <div>
        <div className="font-mono text-sm font-bold" style={{ color: risk.color }}>
          {risk.label.toUpperCase()}
        </div>
        {/* Subtítulo que amarra o nível à ação na carteira (audit M2) */}
        <div className="mt-0.5 text-[11px] leading-snug text-text-secondary">
          {risk.hint}
        </div>
      </div>

      {/* Gradient bar */}
      <div className="relative">
        <div
          className="h-2 w-full rounded-full"
          style={{
            background:
              'linear-gradient(to right, #ef4444 0%, #fca5a5 33%, #93c5fd 66%, #1d4ed8 100%)',
          }}
        />
        {/* Needle */}
        <div
          className="absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow-lg ring-1 ring-black/30"
          style={{ left: `${risk.position}%` }}
        />
      </div>

      {/* Labels under bar */}
      <div className="flex justify-between font-mono text-[8px] leading-tight text-text-secondary">
        <span>STRONG<br />OFF</span>
        <span className="text-center">MILD<br />OFF</span>
        <span className="text-center">MILD<br />ON</span>
        <span className="text-right">STRONG<br />ON</span>
      </div>

      {/* Last inflection section */}
      {inflectionDate && (
        <div className="mt-auto border-t border-border-line pt-3">
          <div className="font-mono text-[8px] tracking-widest text-text-secondary">
            LAST INFLECTION POINT
          </div>
          <div className="mt-1 font-mono text-xs text-text-primary">
            {inflectionDate}
          </div>
        </div>
      )}
    </div>
  )
}
