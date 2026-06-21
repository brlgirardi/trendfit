import type {
  AssetData,
  ChatMessage,
  ChatReply,
  ChatSession,
  ConeData,
  MacroData,
} from './types'

// BASE vazio: o proxy do Vite reescreve /api -> http://localhost:8502.
const BASE = ''

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Falha em ${path}: ${res.status} ${res.statusText}`)
  }
  return (await res.json()) as T
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    // Tenta extrair a mensagem amigável do backend (detail.error) antes de cair no genérico.
    let msg = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      const detail = data?.detail
      if (detail?.error) msg = detail.error
      else if (typeof detail === 'string') msg = detail
    } catch {
      /* corpo não-JSON: mantém msg genérica */
    }
    throw new Error(msg)
  }
  return (await res.json()) as T
}

/** Lista de ativos disponíveis (ex.: ["BTC", "ETH", "Ouro", "SP500"]). */
export async function fetchAssets(): Promise<string[]> {
  return getJSON<string[]>('/api/assets')
}

/** Dados completos de um ativo: OHLCV + sinais + postura + walk-forward. */
export async function fetchAssetData(asset: string): Promise<AssetData> {
  return getJSON<AssetData>(`/api/data/${encodeURIComponent(asset)}`)
}

/** Séries macro (FNG, VIX, DXY, US10Y, MVRV, funding). */
export async function fetchMacro(): Promise<MacroData> {
  return getJSON<MacroData>('/api/macro')
}

/** Cone do mercado de apostas (Kalshi + Polymarket) p/ um ativo.
 *  ESPELHO DA MULTIDÃO, nunca sinal do sistema. `available:false` se a rede cair. */
export async function fetchCone(asset: string): Promise<ConeData> {
  return getJSON<ConeData>(`/api/cone/${encodeURIComponent(asset)}`)
}

// ── Buffett Jr (chat) ────────────────────────────────────────────────────────

/** Manda uma mensagem ao Buffett Jr. `asset` é o ativo em foco na tela.
 *  `image` é um data URL base64 opcional (print de gráfico arrastado pro chat). */
export async function sendChat(
  message: string,
  session: string | null,
  asset: string | null,
  image: string | null = null,
): Promise<ChatReply> {
  return postJSON<ChatReply>('/api/buffett/chat', { message, session, asset, image })
}

/** Lista as conversas anteriores (mais recentes primeiro). */
export async function fetchSessions(): Promise<ChatSession[]> {
  return getJSON<ChatSession[]>('/api/buffett/sessions')
}

/** Histórico cronológico de uma conversa. */
export async function fetchHistory(session: string): Promise<ChatMessage[]> {
  return getJSON<ChatMessage[]>(
    `/api/buffett/history/${encodeURIComponent(session)}`,
  )
}

/** Cria um id de conversa nova (em branco). */
export async function newSession(): Promise<string> {
  const r = await postJSON<{ session: string }>('/api/buffett/session', {})
  return r.session
}
