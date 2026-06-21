import { useEffect, useState } from 'react'
import { fetchAssetData } from '../api/client'
import type { AssetData } from '../api/types'

interface UseAssetDataResult {
  data: AssetData | null
  loading: boolean
  error: string | null
}

/** Carrega os dados do ativo selecionado e refaz o fetch quando `asset` muda. */
export function useAssetData(asset: string): UseAssetDataResult {
  const [data, setData] = useState<AssetData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!asset) {
      setData(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    fetchAssetData(asset)
      .then((res) => {
        if (cancelled) return
        setData(res)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setData(null)
        setError(err instanceof Error ? err.message : 'Erro desconhecido')
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [asset])

  return { data, loading, error }
}
