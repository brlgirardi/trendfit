import { useEffect, useRef, useState } from 'react'
import {
  Send,
  Plus,
  History,
  MessageSquare,
  Loader2,
  TriangleAlert,
  ImagePlus,
  X,
  Copy,
  Check,
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

// ── Markdown leve (parsing seguro, sem dependência externa) ───────────────────
// Converte um subconjunto de Markdown para elementos React. O texto entra como
// string e sai como nós React (que escapam o conteúdo por padrão), então NUNCA
// usamos dangerouslySetInnerHTML — marcadores são aplicados via tokenização.

// Aplica os marcadores inline (**bold**, *italic*/_italic_, `code`) a um trecho.
// Retorna um array de nós React. O texto puro vira string (escapado pelo React).
function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = []
  // Ordem importa: code primeiro (não interpreta marcadores dentro de crase),
  // depois bold (**), depois italic (* ou _).
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  let i = 0

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index))
    }
    const token = match[0]
    const key = `${keyPrefix}-i${i++}`

    if (token.startsWith('`') && token.endsWith('`')) {
      nodes.push(
        <code
          key={key}
          className="rounded bg-bg-primary px-1 py-0.5 font-mono text-[0.85em] text-text-primary"
        >
          {token.slice(1, -1)}
        </code>,
      )
    } else if (token.startsWith('**') && token.endsWith('**')) {
      nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('*') && token.endsWith('*')) {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>)
    } else if (token.startsWith('_') && token.endsWith('_')) {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>)
    } else {
      nodes.push(token)
    }
    lastIndex = pattern.lastIndex
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex))
  }
  return nodes
}

// Quebra o texto em blocos (parágrafos e listas com '- ') e renderiza cada um.
function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n')
  const blocks: React.ReactNode[] = []
  let listItems: string[] = []
  let paragraph: string[] = []
  let blockKey = 0

  function flushParagraph() {
    if (paragraph.length === 0) return
    const key = `p-${blockKey++}`
    const inner: React.ReactNode[] = []
    paragraph.forEach((ln, idx) => {
      if (idx > 0) inner.push(<br key={`${key}-br${idx}`} />)
      inner.push(...renderInline(ln, `${key}-l${idx}`))
    })
    blocks.push(
      <p key={key} className="m-0">
        {inner}
      </p>,
    )
    paragraph = []
  }

  function flushList() {
    if (listItems.length === 0) return
    const key = `ul-${blockKey++}`
    blocks.push(
      <ul key={key} className="m-0 list-disc space-y-0.5 pl-5">
        {listItems.map((item, idx) => (
          <li key={`${key}-li${idx}`}>{renderInline(item, `${key}-li${idx}`)}</li>
        ))}
      </ul>,
    )
    listItems = []
  }

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '')
    const listMatch = /^\s*[-*]\s+(.*)$/.exec(line)
    if (listMatch) {
      flushParagraph()
      listItems.push(listMatch[1])
      continue
    }
    if (line.trim() === '') {
      flushParagraph()
      flushList()
      continue
    }
    flushList()
    paragraph.push(line)
  }
  flushParagraph()
  flushList()

  return <div className="space-y-2">{blocks}</div>
}

export function BuffettChat({ asset }: BuffettChatProps) {
  const [session, setSession] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [image, setImage] = useState<string | null>(null) // data URL anexado
  const [dragOver, setDragOver] = useState(false)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)

  const scrollRef = useRef<HTMLDivElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

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

  // Auto-resize do textarea: cresce com o conteúdo até o teto (max-h-28).
  function resizeTextarea() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  // Reajusta quando o input muda por código (ex.: limpa ao enviar / nova conversa).
  useEffect(() => {
    resizeTextarea()
  }, [input])

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
    // Envia se houver texto OU imagem anexada (só a imagem já é um pedido).
    if ((!text && !image) || sending) return

    const img = image
    const userMsg: ChatMessage = {
      role: 'user',
      content: text || (img ? '(imagem)' : ''),
      image: img ?? undefined,
    }
    setMessages((cur) => [...cur, userMsg])
    setInput('')
    setImage(null)
    setSending(true)
    setError(null)
    // Reseta a altura do textarea ao enviar (volta a 1 linha).
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    try {
      const res = await sendChat(text, session, asset, img)
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

  // Copia o conteúdo de uma mensagem do assistant; mostra Check por ~1.5s.
  async function handleCopy(idx: number, content: string) {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedIdx(idx)
      window.setTimeout(() => {
        setCopiedIdx((cur) => (cur === idx ? null : cur))
      }, 1500)
    } catch {
      /* clipboard pode falhar (permissão/contexto inseguro); silencioso */
    }
  }

  // ── Imagem: drag-drop, colar (paste) e anexar (botão) ────────────────────────
  function readImageFile(file: File) {
    if (!file.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = () => setImage(typeof reader.result === 'string' ? reader.result : null)
    reader.readAsDataURL(file) // vira data URL base64
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = Array.from(e.dataTransfer.files).find((f) => f.type.startsWith('image/'))
    if (file) readImageFile(file)
  }

  function handlePaste(e: React.ClipboardEvent) {
    const item = Array.from(e.clipboardData.items).find((it) => it.type.startsWith('image/'))
    const file = item?.getAsFile()
    if (file) {
      e.preventDefault()
      readImageFile(file)
    }
  }

  return (
    <div
      onDrop={handleDrop}
      onDragOver={(e) => {
        e.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={(e) => {
        e.preventDefault()
        setDragOver(false)
      }}
      className={`relative flex h-full flex-col rounded-lg border bg-bg-panel ${
        sending ? 'ai-glow border-transparent' : 'border-border-line'
      }`}
    >
      {/* Overlay de arrastar imagem */}
      {dragOver && (
        <div className="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[#a855f7] bg-bg-primary/80">
          <ImagePlus className="text-[#a855f7]" size={28} />
          <span className="font-mono text-sm text-text-primary">
            Solta a imagem aqui
          </span>
        </div>
      )}

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
        {messages.map((m, i) => {
          const isAssistant = m.role === 'assistant'
          // Markdown leve só nas respostas do assistant; welcome e user seguem texto puro.
          const isWelcome = isAssistant && m.content === WELCOME.content
          const copyable = isAssistant && !isWelcome && m.content.trim().length > 0
          return (
            <div
              key={i}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`group relative max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'whitespace-pre-wrap bg-bull/15 text-text-primary'
                    : 'bg-bg-primary text-text-primary'
                } ${copyable ? 'pr-8' : ''}`}
              >
                {m.image && (
                  <img
                    src={m.image}
                    alt="anexo"
                    className="mb-2 max-h-40 rounded-md border border-border-line"
                  />
                )}
                {isAssistant && !isWelcome ? (
                  renderMarkdown(m.content)
                ) : (
                  <span className="whitespace-pre-wrap">{m.content}</span>
                )}

                {copyable && (
                  <button
                    onClick={() => handleCopy(i, m.content)}
                    title={copiedIdx === i ? 'Copiado' : 'Copiar resposta'}
                    className="absolute right-1.5 top-1.5 rounded p-1 text-text-secondary opacity-0 transition-opacity hover:bg-bg-panel hover:text-text-primary focus:opacity-100 group-hover:opacity-100"
                  >
                    {copiedIdx === i ? (
                      <Check size={13} className="text-bull" />
                    ) : (
                      <Copy size={13} />
                    )}
                  </button>
                )}
              </div>
            </div>
          )
        })}

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
        {/* Preview da imagem anexada */}
        {image && (
          <div className="mb-2 inline-flex items-start gap-2 rounded-md border border-border-line bg-bg-primary p-1.5">
            <img src={image} alt="anexo" className="max-h-16 rounded" />
            <button
              onClick={() => setImage(null)}
              title="Remover imagem"
              className="rounded p-0.5 text-text-secondary hover:bg-bg-panel hover:text-bear"
            >
              <X size={14} />
            </button>
          </div>
        )}

        <div className="flex items-end gap-2">
          {/* Anexar imagem */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) readImageFile(f)
              e.target.value = '' // permite reanexar o mesmo arquivo
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            title="Anexar imagem (ou arraste / cole)"
            className="rounded-md p-2 text-text-secondary transition-colors hover:bg-bg-primary hover:text-text-primary"
          >
            <ImagePlus size={16} />
          </button>

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              resizeTextarea()
            }}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={`Pergunta sobre ${asset} ou arraste uma imagem...`}
            rows={1}
            className="max-h-28 flex-1 resize-none overflow-y-auto rounded-md border border-border-line bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:border-bull focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={sending || (input.trim().length === 0 && !image)}
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
