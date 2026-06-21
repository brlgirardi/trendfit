// Tipos compartilhados do contrato de dados entre o backend TrendFit e o cockpit.

export interface OHLCVBar {
  /** Unix timestamp em segundos (UTC), aceito pelo lightweight-charts. */
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export type Regime = 'BULL' | 'BEAR' | 'OUT'

export interface Signal {
  time: number
  regime: Regime
  in_position: boolean
  /** Fração alocada [0..1]. */
  fraction: number
  /** Stop de trailing (ATR) corrente, ou null quando fora de posição. */
  trailing_stop: number | null
}

export interface Posture {
  /** Ex.: "ACUMULAR" | "NEUTRO" | "CAUTELOSO" | "DEFENSIVO". */
  label: string
  /** Ação sugerida (texto livre). */
  action: string
  /** Ambiente macro ("FAVORÁVEL" | "MISTO" | "ADVERSO"). */
  environment: string
  /** Cor hex já resolvida pelo backend (fallback no front). */
  color: string
}

export interface Valuation {
  /** Rótulo pronto do backend (ex.: "CAPE 42", "MVRV 1.21"); "" quando ausente. */
  label: string
  /** Percentil histórico [0..100], ou null quando não há valuation para o ativo. */
  pct: number | null
}

export interface WalkForward {
  /** Retorno out-of-sample (fração, ex.: 1.568 = +156,8%). */
  oos_return: number
  sharpe: number
  /** Max drawdown (fração negativa, ex.: -0.33). */
  max_dd: number
  /** CAGR (fração). */
  cagr: number
  /** Janela OOS, ex.: "2021-2025". */
  period: string
}

export interface AssetData {
  asset: string
  ohlcv: OHLCVBar[]
  signals: Signal[]
  posture: Posture
  valuation: Valuation
  walkforward: WalkForward | null
}

export interface ConePoint {
  /** Direção da aposta: tocar acima ('up') ou abaixo ('down') do preço de hoje. */
  dir: 'up' | 'down'
  /** Alvo de preço precificado pelo mercado. */
  target: number
  /** Probabilidade implícita [0..1]. */
  prob: number
  /** Fonte do mercado de aposta (ex.: 'kalshi' | 'polymarket'). */
  source: string
  /** Open interest (Kalshi); null quando a fonte não expõe (Polymarket). */
  oi: number | null
}

export interface ConeData {
  asset: string
  points: ConePoint[]
  sources: string[]
  /** Horizonte/resolução do mercado (ISO date) ou null se indisponível. */
  end: string | null
  /** false quando a rede externa caiu ou não há mercado p/ o ativo. */
  available: boolean
}

export interface MacroPoint {
  time: number
  value: number
}

export interface MacroData {
  fng: MacroPoint[]
  vix: MacroPoint[]
  dxy: MacroPoint[]
  us10y: MacroPoint[]
  mvrv_btc: MacroPoint[]
  mvrv_eth: MacroPoint[]
  funding: MacroPoint[]
}

// ── Buffett Jr (chat) ────────────────────────────────────────────────────────

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  /** ISO timestamp (ausente em mensagens otimistas locais ainda não persistidas). */
  created_at?: string
  /** Thumb (data URL) da imagem anexada — só na bolha local; não persiste no backend. */
  image?: string
}

export interface ChatSession {
  session: string
  /** Rótulo da sidebar (1ª mensagem do usuário, truncada). */
  title: string
  message_count: number
  last_at: string
}

export interface ChatReply {
  reply: string
  session: string
}
