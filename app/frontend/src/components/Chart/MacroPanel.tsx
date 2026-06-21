import { useEffect, useRef, useState } from 'react'
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { MacroPoint } from '../../api/types'

interface MacroPanelProps {
  label: string
  data: MacroPoint[]
  color?: string
  /** Casas decimais do valor exibido (F&G/VIX inteiros; US10Y/MVRV 2 casas). */
  precision?: number
}

export function MacroPanel({ label, data, color = '#00FF88', precision = 1 }: MacroPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  // Valor sob o cursor (hover) e o último valor da série (estado atual). Antes os
  // mini-gráficos não exibiam número nenhum — só a linha.
  const [hoverVal, setHoverVal] = useState<number | null>(null)
  const last = data.length > 0 ? data[data.length - 1].value : null
  const shown = hoverVal ?? last

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const chart: IChartApi = createChart(el, {
      width: el.clientWidth,
      height: 120,
      layout: {
        background: { type: ColorType.Solid, color: '#1A1A1A' },
        textColor: '#888888',
        fontFamily: 'JetBrains Mono, monospace',
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#222222' },
      },
      rightPriceScale: { visible: false },
      leftPriceScale: { visible: false },
      timeScale: { borderColor: '#2A2A2A', timeVisible: false },
      crosshair: { mode: CrosshairMode.Magnet },
      handleScroll: false,
      handleScale: false,
    })

    const line = chart.addLineSeries({
      color,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    line.setData(
      (data ?? []).map((p) => ({ time: p.time as UTCTimestamp, value: p.value })),
    )
    chart.timeScale().fitContent()

    // Lê o valor da série sob o cursor e mostra no header.
    chart.subscribeCrosshairMove((param) => {
      const pt = param.seriesData.get(line) as { value?: number } | undefined
      setHoverVal(pt && typeof pt.value === 'number' ? pt.value : null)
    })

    const handleResize = () => chart.applyOptions({ width: el.clientWidth })
    const ro = new ResizeObserver(handleResize)
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [data, color])

  return (
    <div className="relative rounded-lg border border-border-line bg-bg-panel p-2">
      <div className="absolute left-3 top-2 z-10 font-mono text-xs font-medium uppercase tracking-wide text-text-secondary">
        {label}
      </div>
      {/* Valor atual (ou sob o cursor) — antes não havia número legível. */}
      <div
        className="absolute right-3 top-2 z-10 font-mono text-sm font-bold tabular-nums"
        style={{ color }}
      >
        {shown != null ? shown.toFixed(precision) : '—'}
      </div>
      <div ref={containerRef} className="h-[120px] w-full" />
    </div>
  )
}
