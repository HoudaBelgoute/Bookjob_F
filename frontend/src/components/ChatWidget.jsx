import { Plus, Send, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { AI_QUESTIONS } from '../data/data'
import { useStore } from '../store/useStore'

function Bubble({ role, children }) {
  const mine = role === 'user'
  return (
    <div className={mine ? 'flex justify-end' : 'flex items-start gap-2'}>
      {!mine && (
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-navy-900 text-gold">
          <Sparkles size={13} />
        </span>
      )}
      <p
        className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
          mine ? 'rounded-br-md bg-primary text-white' : 'rounded-tl-md bg-chip text-ink'
        }`}
      >
        {children}
      </p>
    </div>
  )
}

// Petit chatbot flottant (remplace l'ancienne page « Assistant IA »).
export default function ChatWidget() {
  const {
    chatOpen, setChatOpen, chats, activeChat, newChat, removeChat, sendMessage,
    activeCompanyId, allCompanies, openCompany, meta, profile,
  } = useStore()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)
  const chat = chats.find((c) => c.id === activeChat) || null
  const company = allCompanies.find((c) => c.id === activeCompanyId) || null
  const messages = chat?.messages || []

  useEffect(() => {
    if (chatOpen) endRef.current?.scrollIntoView({ block: 'end' })
  }, [chatOpen, messages.length, busy])

  useEffect(() => {
    if (!chatOpen) return undefined
    inputRef.current?.focus()
    const onKey = (e) => e.key === 'Escape' && setChatOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [chatOpen, setChatOpen])

  const send = async (value) => {
    const v = value.trim()
    if (!v || busy) return
    setText('')
    setBusy(true)
    await sendMessage(v, company?.id)
    setBusy(false)
  }

  if (!chatOpen) {
    return (
      <button
        type="button"
        onClick={() => setChatOpen(true)}
        className="fixed bottom-6 right-6 z-30 flex items-center gap-2.5 rounded-full bg-navy-900 px-5 py-3.5 text-[14px] font-semibold text-white shadow-fab hover:bg-navy-800"
      >
        <Sparkles size={18} className="text-gold" />
        Assistant IA
      </button>
    )
  }

  const first = profile.nom ? ` ${profile.nom.split(' ')[0]}` : ''
  const greeting = `Bonjour${first} ! Je peux t’aider à comprendre une entreprise, comparer ton profil à son secteur ou préparer ta candidature.${
    meta?.ai?.enabled ? '' : ' (Aucune clé IA configurée : mes réponses se limitent aux données disponibles.)'
  }`

  return (
    <section
      role="dialog"
      aria-label="Assistant IA"
      className="fixed inset-x-3 bottom-3 z-40 flex h-[min(600px,calc(100vh-1.5rem))] flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-pop sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-[390px]"
    >
      <header className="flex items-center gap-3 bg-navy-900 px-4 py-3 text-white">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-gold"><Sparkles size={17} /></span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold leading-tight">Assistant IA</h2>
          <p className="truncate text-[11px] text-[#9fb2d0]">{meta?.ai?.enabled ? `IA : ${meta.ai.provider}` : 'Mode sans IA'}</p>
        </div>
        <button type="button" onClick={newChat} aria-label="Nouvelle conversation" title="Nouvelle conversation" className="rounded-lg p-2 text-[#c9d6ea] hover:bg-white/10 hover:text-white"><Plus size={18} /></button>
        {chat && messages.length > 0 && (
          <button
            type="button"
            onClick={() => window.confirm('Supprimer cette conversation ?') && removeChat(chat.id)}
            aria-label="Supprimer la conversation"
            title="Supprimer la conversation"
            className="rounded-lg p-2 text-[#c9d6ea] hover:bg-white/10 hover:text-white"
          ><Trash2 size={17} /></button>
        )}
        <button type="button" onClick={() => setChatOpen(false)} aria-label="Fermer l’assistant" className="rounded-lg p-2 text-[#c9d6ea] hover:bg-white/10 hover:text-white"><X size={18} /></button>
      </header>

      {company && (
        <div className="flex items-center gap-2 border-b border-line bg-primary-soft px-4 py-2 text-[12px]">
          <span className="min-w-0 flex-1 truncate">Contexte : <strong>{company.short}</strong></span>
          <button type="button" className="font-semibold text-primary" onClick={() => openCompany(null)}>Retirer</button>
        </div>
      )}

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
        <Bubble role="assistant">{greeting}</Bubble>
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2 pl-9">
            {AI_QUESTIONS.map((q) => (
              <button key={q} type="button" onClick={() => send(q)} className="rounded-full border border-line px-3 py-1.5 text-left text-[12px] text-primary hover:bg-primary-soft">{q}</button>
            ))}
          </div>
        )}
        {messages.map((m) => <Bubble key={m.id} role={m.role}>{m.content}</Bubble>)}
        {busy && <Bubble role="assistant">L’assistant écrit…</Bubble>}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(text) }} className="border-t border-line p-3">
        <div className="flex overflow-hidden rounded-xl border border-line focus-within:border-primary">
          <input
            ref={inputRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Pose une question…"
            aria-label="Ta question"
            className="min-w-0 flex-1 px-3.5 py-3 text-[14px] outline-none placeholder:text-faint"
          />
          <button type="submit" disabled={busy || !text.trim()} aria-label="Envoyer" className="bg-primary px-4 text-white hover:bg-primary-hover disabled:opacity-50"><Send size={17} /></button>
        </div>
        <p className="mt-2 text-center text-[10.5px] text-muted">L’assistant peut faire des erreurs. Vérifie les informations importantes.</p>
      </form>
    </section>
  )
}
