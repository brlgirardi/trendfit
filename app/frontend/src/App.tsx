import { useEffect, useMemo, useState } from 'react'
import { Activity, Loader2, TriangleAlert } from 'lucide-react'
import { fetchAssets } from './api/client'
import { useAssetData } from './hooks/useAssetData'
import { useMacroData } from './hooks/useMacroData'
import { PostureBadge } from './components/PostureBadge'
import { LeverageBadge } from './components/LeverageBadge'
import { RiskGauge } from './components/RiskGauge'
import { DecisionBar } from './components/DecisionBar'
import { BuffettChat } from './components/BuffettChat'
import { MainChart } from './components/Chart/MainChart'
import { RegimeTimeline } from './components/Chart/RegimeTimeline'
import { RegimeLegend } from './components/Chart/RegimeLegend'
import { MacroPanel } from './components/Chart/MacroPanel'
import { AssetSelector } from './components/Controls/AssetSelector'
import { SystemSelector, type SystemId } from './components/Controls/SystemSelector'
import type { Signal } from './api/types'

const FALLBACK_ASSETS = ['BTC', 'ETH', 'Ouro', 'SP500']

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-3 text-text-secondary">
      <Loader2 className="animate-spin" size={28} />
      <span className="font-mono text-sm">{label}</span>
    </div>
  )
}

function lastSignal(signals: Signal[]): Signal | null {
  return signals.length > 0 ? signals[signals.length - 1] : null
}

export default function App() {
  const [assets, setAssets] = useState<string[]>(FALLBACK_ASSETS)
  const [selected, setSelected] = useState<string>(FALLBACK_ASSETS[0])
  const [system, setSystem] = useState<SystemId>('trendfit')

  const { data, loading, error } = useAssetData(selected)
  const { data: macro } = useMacroData()

  // Carrega a lista real de ativos; mantem o fallback se a API falhar.
  useEffect(() => {
    let cancelled = false
    fetchAssets()
      .then((list) => {
        if (cancelled || !Array.isArray(list) || list.length === 0) return
        setAssets(list)
        setSelected((cur) => (list.includes(cur) ? cur : list[0]))
      })
      .catch(() => {
        /* mantem FALLBACK_ASSETS */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const sig = useMemo(
    () => (data ? lastSignal(data.signals) : null),
    [data],
  )

  // MVRV correto conforme o ativo (ETH usa serie propria).
  const mvrvSeries = useMemo(() => {
    if (!macro) return []
    return selected.toUpperCase() === 'ETH' ? macro.mvrv_eth : macro.mvrv_btc
  }, [macro, selected])

  const mvrvLabel =
    selected.toUpperCase() === 'ETH' ? 'MVRV ETH' : 'MVRV BTC'

  return (
    <div className="flex h-screen flex-col bg-bg-primary text-text-primary">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border-line px-6 py-4">
        <div className="flex items-center gap-3">
          <Activity className="text-bull" size={22} />
          <h1 className="text-xl font-bold tracking-tight">TrendFit Cockpit</h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <AssetSelector
            assets={assets}
            selected={selected}
            onChange={setSelected}
          />
          <SystemSelector selected={system} onChange={setSystem} />
        </div>
      </header>

      {/* Row de badges */}
      <div className="flex flex-wrap items-center gap-4 border-b border-border-line px-6 py-3">
        {data ? (
          <>
            <PostureBadge posture={data.posture} />
            <LeverageBadge
              regime={sig?.regime ?? 'OUT'}
              fraction={sig?.fraction ?? 0}
            />
            {data.walkforward ? (
              <div className="ml-auto flex items-center gap-5 font-mono text-xs text-text-secondary">
                <span>
                  OOS{' '}
                  <span className="text-text-primary">
                    {(data.walkforward.oos_return * 100).toFixed(1)}%
                  </span>
                </span>
                <span>
                  Sharpe{' '}
                  <span className="text-text-primary">
                    {data.walkforward.sharpe.toFixed(2)}
                  </span>
                </span>
                <span>
                  MaxDD{' '}
                  <span className="text-bear">
                    {(data.walkforward.max_dd * 100).toFixed(1)}%
                  </span>
                </span>
                <span className="opacity-70">{data.walkforward.period}</span>
              </div>
            ) : null}
          </>
        ) : (
          <span className="font-mono text-sm text-text-secondary">
            {loading ? 'carregando postura...' : '—'}
          </span>
        )}
      </div>

      {/* Conteudo principal: sistema (esquerda) + assessor Buffett Jr (direita) */}
      <main className="flex min-h-0 flex-1 gap-4 overflow-hidden p-6">
        {/* Coluna esquerda: gráfico do sistema + macro */}
        <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-auto">
          {error ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-bear">
              <TriangleAlert size={32} />
              <p className="font-mono text-sm">{error}</p>
              <p className="max-w-md text-center text-xs text-text-secondary">
                Verifique se o backend está rodando em localhost:8502 (proxy /api).
              </p>
            </div>
          ) : loading || !data ? (
            <div className="flex-1">
              <Spinner label="carregando dados do ativo..." />
            </div>
          ) : (
            <>
              {/* Linha de decisão do dia (audit A4) — primeira coisa que o Bruno vê */}
              <DecisionBar asset={selected} data={data} />

              {/* Área do gráfico + Risk Gauge lateral */}
              <div className="flex h-[60%] min-h-[300px] gap-4">
                <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <div className="flex-1 overflow-hidden rounded-lg border border-border-line bg-bg-primary">
                    <MainChart data={data} />
                  </div>
                  {/* Timeline de regime abaixo do gráfico */}
                  <RegimeTimeline signals={data.signals} />
                  {/* Legenda das cores das zonas (audit A1) */}
                  <RegimeLegend />
                </div>
                {/* Risk Gauge lateral */}
                <div className="w-44 shrink-0">
                  <RiskGauge signals={data.signals} />
                </div>
              </div>

              {/* Grid 2 colunas de MacroPanel */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <MacroPanel
                  label="Fear & Greed"
                  data={macro?.fng ?? []}
                  color="#FFB800"
                  precision={0}
                />
                <MacroPanel
                  label={mvrvLabel}
                  data={mvrvSeries}
                  color="#00FF88"
                  precision={2}
                />
                <MacroPanel
                  label="VIX"
                  data={macro?.vix ?? []}
                  color="#FF3B3B"
                  precision={1}
                />
                <MacroPanel
                  label="US 10Y"
                  data={macro?.us10y ?? []}
                  color="#3b82f6"
                  precision={2}
                />
              </div>
            </>
          )}
        </div>

        {/* Coluna direita: chat do Buffett Jr (vê o ativo em foco) */}
        <aside className="hidden w-[360px] shrink-0 lg:block">
          <BuffettChat asset={selected} />
        </aside>
      </main>
    </div>
  )
}
