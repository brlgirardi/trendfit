import type { AssetData, Signal } from '../api/types'

interface DecisionBarProps {
  asset: string
  data: AssetData
}

interface Decision {
  regimeLabel: string
  regimeColor: string
  action: string
}

// Leitura MECANICA do estado do sistema (audit A4). Descreve o que o sistema
// esta fazendo HOJE — nao e ordem ao Bruno (linha vermelha: regime decide timing,
// Bruno decide a acao).
function readDecision(sig: Signal | null): Decision {
  if (!sig)
    return { regimeLabel: 'SEM DADO', regimeColor: '#888888', action: 'aguardando' }
  if (sig.regime === 'BULL' && sig.fraction >= 0.8)
    return { regimeLabel: 'BULL', regimeColor: '#00FF88', action: `comprado · posição cheia (${Math.round(sig.fraction * 100)}%)` }
  if (sig.regime === 'BULL')
    return { regimeLabel: 'BULL', regimeColor: '#00FF88', action: `comprado parcial (${Math.round(sig.fraction * 100)}%)` }
  if (sig.regime === 'BEAR')
    return { regimeLabel: 'BEAR', regimeColor: '#FF3B3B', action: 'fora · preserva capital' }
  return { regimeLabel: 'OUT', regimeColor: '#FFB800', action: 'fora · aguarda sinal' }
}

export function DecisionBar({ asset, data }: DecisionBarProps) {
  const sig = data.signals.length > 0 ? data.signals[data.signals.length - 1] : null
  const d = readDecision(sig)
  const posture = data.posture

  // Preço de hoje e variação diária — lidos do último candle (display-only).
  const bars = data.ohlcv
  const lastBar = bars.length > 0 ? bars[bars.length - 1] : null
  const prevBar = bars.length > 1 ? bars[bars.length - 2] : null
  const chgPct =
    lastBar && prevBar && prevBar.close !== 0
      ? ((lastBar.close - prevBar.close) / prevBar.close) * 100
      : null
  const chgColor = chgPct == null ? '#888888' : chgPct >= 0 ? '#00FF88' : '#FF3B3B'
  const fmtPrice = (v: number) =>
    v >= 100 ? v.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) : v.toFixed(2)

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border-line bg-bg-panel px-4 py-2.5">
      <span className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
        Decisão hoje
      </span>
      <span className="font-mono text-sm font-bold text-text-primary">{asset}</span>
      {lastBar ? (
        <>
          <span className="font-mono text-sm font-bold text-text-primary tabular-nums">
            {fmtPrice(lastBar.close)}
          </span>
          {chgPct != null ? (
            <span
              className="font-mono text-xs font-bold tabular-nums"
              style={{ color: chgColor }}
            >
              {chgPct >= 0 ? '+' : ''}
              {chgPct.toFixed(2)}%
            </span>
          ) : null}
        </>
      ) : null}
      <span className="text-text-secondary">·</span>
      {/* Regime: o motor mecânico que decide o timing */}
      <span
        className="rounded px-1.5 py-0.5 font-mono text-xs font-bold"
        style={{ color: d.regimeColor, backgroundColor: `${d.regimeColor}1f` }}
      >
        {d.regimeLabel}
      </span>
      <span className="text-text-secondary">·</span>
      {/* Ação mecânica do sistema (estado, não ordem) */}
      <span className="text-sm text-text-primary">sistema {d.action}</span>
      <span className="text-text-secondary">·</span>
      {/* Postura: contexto que informa (não decide timing) */}
      <span className="text-sm" style={{ color: posture.color }}>
        postura {posture.label || '—'}
      </span>
      {posture.environment ? (
        <span className="font-mono text-[11px] text-text-secondary">
          · ambiente {posture.environment}
        </span>
      ) : null}
    </div>
  )
}
