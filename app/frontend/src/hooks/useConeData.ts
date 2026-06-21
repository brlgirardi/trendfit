import { useEffect, useState } from 'react'
import { fetchCone } from '../api/client'
import type { ConeData } from '../api/types'

interface UseConeDataResult {
  data: ConeData | null
  loading: boolean
}

/** Carrega o cone do mercado de apostas do ativo selecionado e refaz o fetch
 *  quando `asset` muda. ESPELHO DA MULTIDÃO (Kalshi + Polymarket), nunca sinal
 *  do sistema. Falha de rede degrada para `null` (o painel mostra estado vazio). */
export function useConeData(asset: string): UseConeDataResult {
  const [data, setData] = useState<ConeData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)

  useEffect(() => {
    if (!asset) {
      setData(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)

    fetchCone(asset)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch(() => {
        if (!cancelled) setData(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [asset])

  return { data, loading }
}
