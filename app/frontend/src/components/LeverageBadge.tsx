import { Zap, CheckCircle2, AlertTriangle, OctagonX, Skull } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface LeverageBadgeProps {
  regime: string
  fraction: number
}

interface LeverageState {
  Icon: LucideIcon
  label: string
  color: string
  bg: string
  pulse?: boolean
}

const COLORS = {
  bull: '#00FF88',
  bear: '#FF3B3B',
  neutral: '#FFB800',
  veryBad: '#FF0000',
}

function resolveState(regime: string, fraction: number): LeverageState {
  const r = (regime || '').toUpperCase()

  // Pior nivel: fora de posicao em mercado de baixa.
  if (r === 'BEAR' && fraction <= 0) {
    return {
      Icon: Skull,
      label: 'MUITO RUIM',
      color: COLORS.veryBad,
      bg: 'rgba(255,0,0,0.12)',
      pulse: true,
    }
  }

  if (r === 'BEAR') {
    return {
      Icon: OctagonX,
      label: 'FIQUE FORA',
      color: COLORS.bear,
      bg: 'rgba(255,59,59,0.12)',
    }
  }

  if (r === 'OUT') {
    return {
      Icon: AlertTriangle,
      label: 'NEUTRO',
      color: COLORS.neutral,
      bg: 'rgba(255,184,0,0.12)',
    }
  }

  if (r === 'BULL' && fraction >= 0.8) {
    return {
      Icon: Zap,
      label: 'PODE ALAVANCAR',
      color: COLORS.bull,
      bg: 'rgba(0,255,136,0.14)',
    }
  }

  if (r === 'BULL' && fraction > 0) {
    return {
      Icon: CheckCircle2,
      label: 'COMPRADO',
      color: COLORS.bull,
      bg: 'rgba(0,255,136,0.07)',
    }
  }

  // BULL sem fracao (ou caso residual): neutro.
  return {
    Icon: AlertTriangle,
    label: 'NEUTRO',
    color: COLORS.neutral,
    bg: 'rgba(255,184,0,0.12)',
  }
}

export function LeverageBadge({ regime, fraction }: LeverageBadgeProps) {
  const s = resolveState(regime, fraction)
  const { Icon } = s

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-base font-bold${
        s.pulse ? ' tf-pulse' : ''
      }`}
      style={{ color: s.color, borderColor: s.color, backgroundColor: s.bg }}
    >
      <Icon size={18} strokeWidth={2.4} />
      <span className="tracking-wide">{s.label}</span>
      <span className="font-mono text-xs font-normal opacity-70">
        {(fraction * 100).toFixed(0)}%
      </span>
    </div>
  )
}
