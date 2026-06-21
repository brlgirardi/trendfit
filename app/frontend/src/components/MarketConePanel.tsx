import { useMemo } from 'react'
import { Eye, TrendingUp, TrendingDown, Users } from 'lucide-react'
import type { ConeData, ConePoint } from '../api/types'

interface MarketConePanelProps {
  data: ConeData | null
  loading?: boolean
}

function fmtTarget(v: number): string {
  // Alvos de preço variam muito de escala (ETH ~3k, BTC ~100k). Sem decimais,
  // com separador de milhar — o número exato vem do mercado, não do sistema.
  return v.toLocaleString('pt-BR', { maximumFractionDigits: 0 })
}

function fmtProb(p: number): string {
  return `${(p * 100).toFixed(0)}%`
}

function byProbDesc(a: ConePoint, b: ConePoint): number {
  return b.prob - a.prob
}

function ConeRow({ point }: { point: ConePoint }) {
  const up = point.dir === 'up'
  const color = up ? 'text-bull' : 'text-bear'
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border-line/40 py-1.5 last:border-b-0">
      <div className="flex items-center gap-2 font-mono text-sm">
        {up ? (
          <TrendingUp className="text-bull" size={14} />
        ) : (
          <TrendingDown className="text-bear" size={14} />
        )}
        <span className="text-text-primary tabular-nums">{fmtTarget(point.target)}</span>
        <span className="text-[10px] uppercase tracking-wide text-text-secondary">
          {point.source}
        </span>
      </div>
      <span className={`font-mono text-sm font-bold tabular-nums ${color}`}>
        {fmtProb(point.prob)}
      </span>
    </div>
  )
}

export function MarketConePanel({ data, loading = false }: MarketConePanelProps) {
  const { ups, downs } = useMemo(() => {
    const points = data?.points ?? []
    return {
      ups: points.filter((p) => p.dir === 'up').slice().sort(byProbDesc),
      downs: points.filter((p) => p.dir === 'down').slice().sort(byProbDesc),
    }
  }, [data])

  const hasData = !!data?.available && (ups.length > 0 || downs.length > 0)

  return (
    <div className="rounded-lg border border-border-line bg-bg-panel p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye className="text-neutral" size={16} />
          <span className="font-mono text-xs font-medium uppercase tracking-wide text-text-secondary">
            Cone do mercado preditivo
          </span>
        </div>
        {hasData && data?.end ? (
          <span className="font-mono text-[10px] text-text-secondary">até {data.end}</span>
        ) : null}
      </div>

      {/* LINHA VERMELHA explícita na UI: espelho da multidão, nunca sinal do sistema. */}
      <div className="mb-3 flex items-start gap-2 rounded-md border border-neutral/30 bg-neutral/5 px-2.5 py-2">
        <Users className="mt-0.5 shrink-0 text-neutral" size={13} />
        <p className="text-[11px] leading-snug text-text-secondary">
          Espelho da multidão (Kalshi + Polymarket). É o que apostadores precificam,
          <span className="text-text-primary"> não é sinal do sistema</span> — o motor
          do TrendFit nunca usa esses números.
        </p>
      </div>

      {loading ? (
        <p className="py-4 text-center font-mono text-xs text-text-secondary">
          carregando cone...
        </p>
      ) : !hasData ? (
        <p className="py-4 text-center font-mono text-xs text-text-secondary">
          Sem cone disponível para este ativo.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
          <div>
            <div className="mb-1 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wide text-bull">
              <TrendingUp size={12} /> Tocar acima
            </div>
            {ups.length > 0 ? (
              ups.map((p, i) => <ConeRow key={`up-${p.source}-${p.target}-${i}`} point={p} />)
            ) : (
              <p className="py-1.5 font-mono text-xs text-text-secondary">—</p>
            )}
          </div>
          <div>
            <div className="mb-1 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wide text-bear">
              <TrendingDown size={12} /> Tocar abaixo
            </div>
            {downs.length > 0 ? (
              downs.map((p, i) => <ConeRow key={`down-${p.source}-${p.target}-${i}`} point={p} />)
            ) : (
              <p className="py-1.5 font-mono text-xs text-text-secondary">—</p>
            )}
          </div>
        </div>
      )}

      {hasData && data?.sources?.length ? (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[10px] text-text-secondary">fontes:</span>
          {data.sources.map((s) => (
            <span
              key={s}
              className="rounded border border-border-line px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-text-secondary"
            >
              {s}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
