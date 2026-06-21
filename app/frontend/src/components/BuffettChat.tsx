import { useEffect, useRef, useState } from 'react'
import {
  Send,
  Plus,
  History,
  MessageSquare,
  Loader2,
  TriangleAlert,
} from 'lucide-react'
import {
  sendChat,
  fetchSessions,
  fetchHistory,
  newSession,
} from '../api/client'
import type { ChatMessage, ChatSession } from '../api/types'

interface BuffettChatProps {
  /** Ativo em foco na tela do cockpit — o Buffett "vê a tela" e prioriza ele. */
  asset: string
}

const WELCOME: ChatMessage = {
  role: 'assistant',
  content:
    'Bah, Brunão! Sou o Buffett Jr. Tô vendo o que tu tá olhando no cockpit — '
    + 'pergunta o que quiser do ativo, da postura ou do cenário que eu te dou minha '
    + 'opinião com base nos dados. A decisão é sempre tua.',
}

export function BuffettChat({ asset }: BuffettChatProps) {
  const [session, setSession] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [sessions, setSessions] = useState<ChatSession[]>([])

  const scrollRef = useRef<HTMLDivElement | null>(null)

  // Auto-scroll para a última mensagem.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  // Carrega a lista de conversas ao abrir o histórico.
  useEffect(() => {
    if (!showHistory) return
    let cancelled = false
    fetchSessions()
      .then((list) => {
        if (!cancelled) setSessions(list)
      })
      .catch(() => {
        /* histórico é secundário; silencioso */
      })
    return () => {
      cancelled = true
    }
  }, [showHistory])

  async function handleNewConversation() {
    try {
      const sid = await newSession()
      setSession(sid)
    } catch {
      setSession(null)
    }
    setMessages([WELCOME])
    setError(null)
    setShowHistory(false)
  }

  async function handleLoadSession(sid: string) {
    setShowHistory(false)
    setError(null)
    try {
      const hist = await fetchHistory(sid)
      setSession(sid)
      setMessages(hist.length > 0 ? hist : [WELCOME])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'falha ao carregar conversa')
    }
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || sending) return

    const userMsg: ChatMessage = { role: 'user', content: text }
    setMessages((cur) => [...cur, userMsg])
    setInput('')
    setSending(true)
    setError(null)

    try {
      const res = await sendChat(text, session, asset)
      setSession(res.session)
      setMessages((cur) => [...cur, { role: 'assistant', content: res.reply }])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'falha ao falar com o Buffett Jr')
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div
      className={`flex h-full flex-col rounded-lg border bg-bg-panel ${
        sending ? 'ai-glow border-transparent' : 'border-border-line'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="text-bull" size={16} />
          <span className="text-sm font-bold">Buffett Jr</span>
          <span className="font-mono text-[10px] text-text-secondary">
            · vê {asset}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowHistory((v) => !v)}
            title="Histórico de conversas"
            className={`rounded p-1.5 transition-colors hover:bg-bg-primary ${
              showHistory ? 'text-bull' : 'text-text-secondary'
            }`}
          >
            <History size={15} />
          </button>
          <button
            onClick={handleNewConversation}
            title="Nova conversa"
            className="rounded p-1.5 text-text-secondary transition-colors hover:bg-bg-primary hover:text-text-primary"
          >
            <Plus size={15} />
          </button>
        </div>
      </div>

      {/* Sidebar de histórico (overlay simples) */}
      {showHistory && (
        <div className="max-h-48 overflow-auto border-b border-border-line">
          {sessions.length === 0 ? (
            <p className="px-4 py-3 font-mono text-xs text-text-secondary">
              Nenhuma conversa anterior.
            </p>
          ) : (
            sessions.map((s) => (
              <button
                key={s.session}
                onClick={() => handleLoadSession(s.session)}
                className={`flex w-full flex-col gap-0.5 border-b border-border-line/50 px-4 py-2 text-left transition-colors hover:bg-bg-primary ${
                  s.session === session ? 'bg-bg-primary' : ''
                }`}
              >
                <span className="truncate text-xs text-text-primary">
                  {s.title}
                </span>
                <span className="font-mono text-[10px] text-text-secondary">
                  {s.message_count} msgs · {s.last_at.slice(0, 10)}
                </span>
              </button>
            ))
          )}
        </div>
      )}

      {/* Mensagens */}
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-auto p-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm leading-relaxed ${
                m.role === 'user'
                  ? 'bg-bull/15 text-text-primary'
                  : 'bg-bg-primary text-text-primary'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-lg bg-bg-primary px-3 py-2 text-sm text-text-secondary">
              <Loader2 className="animate-spin" size={14} />
              <span className="font-mono text-xs">Buffett Jr está pensando...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-bear/40 bg-bear/10 px-3 py-2 text-xs text-bear">
            <TriangleAlert size={14} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border-line p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Pergunta sobre ${asset} ou o cenário...`}
            rows={1}
            className="max-h-28 flex-1 resize-none rounded-md border border-border-line bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:border-bull focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={sending || input.trim().length === 0}
            className="rounded-md bg-bull/20 p-2 text-bull transition-colors hover:bg-bull/30 disabled:cursor-not-allowed disabled:opacity-40"
            title="Enviar (Enter)"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
