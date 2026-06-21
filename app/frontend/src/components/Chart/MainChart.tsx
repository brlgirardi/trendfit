import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  LineStyle,
  CrosshairMode,
  type IChartApi,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { AssetData, Signal } from '../../api/types'

interface MainChartProps {
  data: AssetData
}

// Tons calibrados estilo Glassnode: azul vibrante para Risk-On, vermelho
// DESSATURADO para Risk-Off (evita alarme visual constante — audit A2). O marker
// de virada usa cor viva; a area de fundo fica suave.
function zoneColor(sig: Signal): string {
  if (sig.regime === 'BULL' && sig.fraction >= 0.8) return 'rgba(37,99,235,0.30)'
  if (sig.regime === 'BULL') return 'rgba(96,165,250,0.15)'
  if (sig.regime === 'BEAR') return 'rgba(190,72,82,0.20)'
  return 'rgba(165,135,145,0.11)'
}

export function MainChart({ data }: MainChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const chart: IChartApi = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: '#0D0D0D' },
        textColor: '#888888',
        fontFamily: 'JetBrains Mono, monospace',
        attributionLogo: false, // esconde watermark TradingView (audit M3)
      },
      grid: {
        vertLines: { color: '#1A1A1A' },
        horzLines: { color: '#1A1A1A' },
      },
      rightPriceScale: { borderColor: '#2A2A2A' },
      timeScale: { borderColor: '#2A2A2A', timeVisible: true },
      crosshair: { mode: CrosshairMode.Normal },
    })

    // Zona de fundo colorida por regime.
    // Usa o range de preço real dos candles para que as barras preencham
    // exatamente a altura visível do gráfico.
    if (data.signals.length > 0 && data.ohlcv.length > 0) {
      const hi = data.ohlcv.reduce((m, b) => Math.max(m, b.high), 0)
      const lo = data.ohlcv.reduce((m, b) => Math.min(m, b.low), Infinity)

      const zoneSeries = chart.addHistogramSeries({
        priceScaleId: 'right',
        lastValueVisible: false,
        priceLineVisible: false,
        base: lo,
      })
      zoneSeries.setData(
        data.signals.map((s) => ({
          time: s.time as UTCTimestamp,
          value: hi,
          color: zoneColor(s),
        })),
      )
    }

    const hasOHLCV = data.ohlcv.length > 0

    // Markers de ENTRADA (sistema comprou) e SAÍDA (sistema saiu) — derivados da
    // transição de in_position, não de toda troca de regime (audit M1: menos
    // poluição, semântica clara). Entrada = seta verde p/ cima abaixo da barra;
    // saída = seta vermelha p/ baixo acima da barra.
    const markers = []
    for (let i = 1; i < data.signals.length; i++) {
      const prev = data.signals[i - 1]
      const cur = data.signals[i]
      if (!prev.in_position && cur.in_position) {
        markers.push({
          time: cur.time as UTCTimestamp,
          position: 'belowBar' as const,
          color: '#00FF88',
          shape: 'arrowUp' as const,
          text: 'entrada',
        })
      } else if (prev.in_position && !cur.in_position) {
        markers.push({
          time: cur.time as UTCTimestamp,
          position: 'aboveBar' as const,
          color: '#FF3B3B',
          shape: 'arrowDown' as const,
          text: 'saída',
        })
      }
    }

    if (hasOHLCV) {
      const candles = chart.addCandlestickSeries({
        upColor: '#00FF88',
        downColor: '#FF3B3B',
        borderUpColor: '#00FF88',
        borderDownColor: '#FF3B3B',
        wickUpColor: '#00FF88',
        wickDownColor: '#FF3B3B',
      })
      candles.setData(
        data.ohlcv.map((b) => ({
          time: b.time as UTCTimestamp,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        })),
      )
      if (markers.length > 0) candles.setMarkers(markers)
    } else {
      // Sem OHLCV: linha de fechamento derivada dos sinais.
      const line = chart.addLineSeries({ color: '#E8E8E8', lineWidth: 2 })
      line.setData(
        data.signals.map((s) => ({
          time: s.time as UTCTimestamp,
          value: s.trailing_stop ?? 0,
        })),
      )
      if (markers.length > 0) line.setMarkers(markers)
    }

    // Trailing stop pontilhado.
    const stopPoints = data.signals
      .filter((s) => s.trailing_stop != null)
      .map((s) => ({
        time: s.time as UTCTimestamp,
        value: s.trailing_stop as number,
      }))

    if (stopPoints.length > 0) {
      const stopSeries = chart.addLineSeries({
        color: '#FFB800',
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        lastValueVisible: false,
        priceLineVisible: false,
      })
      stopSeries.setData(stopPoints)
    }

    chart.timeScale().fitContent()

    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight })
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [data])

  return <div ref={containerRef} className="h-full w-full" />
}
