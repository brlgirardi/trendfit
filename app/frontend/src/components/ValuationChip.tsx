import { Gauge, Flame } from 'lucide-react'
import type { Valuation } from '../api/types'

interface ValuationChipProps {
  valuation: Valuation
}

// Limite de "caro": percentil >= 90 = valuation em extremo historico.
const EXTREME_PCT = 90

/**
 * Chip de valuation (display-only). Mostra o rotulo pronto do backend
 * (ex.: "CAPE 42", "MVRV 1.21"). Quando o percentil >= 90 destaca em tom de
 * alerta (neutral/bear) sinalizando valuation cara vs. historico.
 *
 * Linha vermelha: valuation INFORMA o quao caro/barato esta o ativo contra a
 * propria historia. NUNCA preve preco nem aciona trade.
 *
 * Nao renderiza nada quando nao ha rotulo (ativo sem valuation real).
 */
export function ValuationChip({ valuation }: ValuationChipProps) {
  const label = valuation?.label?.trim() ?? ''
  if (!label) return null

  const pct = valuation.pct
  const extreme = pct != null && pct >= EXTREME_PCT

  // Caro (extremo) -> bear; resto -> neutro/secundario. Cores do design system.
  const color = extreme ? '#FF3B3B' : '#888888'
  const Icon = extreme ? Flame : Gauge

  const pctText = pct != null ? `${pct.toFixed(0)}` : null
  const title = extreme
    ? `valuation em extremo historico (percentil ${pctText})`
    : pctText != null
      ? `valuation: percentil ${pctText} vs. historico (display-only, nao e sinal)`
      : 'valuation (display-only, nao e sinal)'

  return (
    <div
      className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-mono"
      style={{
        color,
        borderColor: color,
        backgroundColor: `${color}1A`, // ~10% alpha
      }}
      title={title}
    >
      <Icon size={13} />
      <span className="font-semibold tracking-wide">{label}</span>
      {extreme && pctText != null ? (
        <span className="opacity-80">P{pctText}</span>
      ) : null}
    </div>
  )
}
