import { useEffect, useState } from 'react'
import { fetchMacro } from '../api/client'
import type { MacroData } from '../api/types'

interface UseMacroDataResult {
  data: MacroData | null
  loading: boolean
}

/** Carrega as séries macro uma vez na montagem. */
export function useMacroData(): UseMacroDataResult {
  const [data, setData] = useState<MacroData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    fetchMacro()
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
  }, [])

  return { data, loading }
}
