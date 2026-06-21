import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  type IChartApi,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { MacroPoint } from '../../api/types'

interface MacroPanelProps {
  label: string
  data: MacroPoint[]
  color?: string
}

export function MacroPanel({ label, data, color = '#00FF88' }: MacroPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)

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
        attributionLogo: false, // esconde watermark TradingView (audit M3)
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#222222' },
      },
      // Eixo Y oculto: so valor no tooltip/crosshair.
      rightPriceScale: { visible: false },
      leftPriceScale: { visible: false },
      timeScale: { borderColor: '#2A2A2A', timeVisible: false },
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
      (data ?? []).map((p) => ({
        time: p.time as UTCTimestamp,
        value: p.value,
      })),
    )

    chart.timeScale().fitContent()

    const handleResize = () => {
      chart.applyOptions({ width: el.clientWidth })
    }
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
      <div ref={containerRef} className="h-[120px] w-full" />
    </div>
  )
}
