import { Bell, Menu, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { useStore } from '../../store/useStore'

export default function Topbar({ onMenu }) {
  const askAssistant = useStore((s) => s.askAssistant)
  const [open, setOpen] = useState(false)
  const [notifs, setNotifs] = useState([])
  const [notificationsError, setNotificationsError] = useState('')
  const [notificationsLoading, setNotificationsLoading] = useState(false)
  const [notificationRetry, setNotificationRetry] = useState(0)
  useEffect(() => {
    if (!open) return undefined
    let active = true
    setNotificationsLoading(true)
    setNotificationsError('')
    api.notifications()
      .then((r) => {
        if (active) setNotifs(r.items)
      })
      .catch((error) => {
        if (active) setNotificationsError(error.message || 'Impossible de charger les notifications.')
      })
      .finally(() => {
        if (active) setNotificationsLoading(false)
      })
    return () => { active = false }
  }, [open, notificationRetry])
  const ref = useRef(null)

  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-white px-4 py-3.5 md:px-8">
      <button
        type="button"
        onClick={onMenu}
        aria-label="Ouvrir le menu"
        className="rounded-lg p-2 text-ink hover:bg-surface lg:hidden"
      >
        <Menu size={22} />
      </button>
      <span className="demo-pill shrink-0 border border-[#efdfaa] px-3 py-1.5 text-[12px]">
        Données Google Maps
      </span>
      <p className="hidden flex-1 text-[15px] text-muted md:block">Les entreprises viennent de Google Maps ; le suivi des candidatures est manuel.</p>
      <div className="flex-1 md:hidden" />

      <div className="relative" ref={ref}>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label="Notifications"
          aria-expanded={open}
          className="relative flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-white hover:bg-surface"
        >
          <Bell size={20} />
          {notifs.length > 0 && <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-red-500" />}
        </button>
        {open && (
          <div className="absolute right-0 top-14 z-50 max-h-[min(70vh,32rem)] w-[min(20rem,calc(100vw-2rem))] overflow-y-auto rounded-2xl border border-line bg-white p-2 shadow-pop">
            <p className="px-3 py-2 text-[13px] font-semibold text-muted">Notifications</p>
            {notificationsLoading && <p role="status" className="px-3 py-3 text-[13px] text-muted">Chargement…</p>}
            {notificationsError && (
              <div className="px-3 py-3">
                <p role="alert" className="text-[13px] text-red-700">{notificationsError}</p>
                <button type="button" className="mt-2 text-[12px] font-semibold text-primary underline" onClick={() => setNotificationRetry((retry) => retry + 1)}>Réessayer</button>
              </div>
            )}
            {!notificationsLoading && !notificationsError && notifs.length === 0 && <p className="px-3 py-3 text-[13px] text-muted">Aucune notification.</p>}
            {!notificationsLoading && !notificationsError && notifs.map((n) => (
              <Link key={n.id} to={n.link} onClick={() => setOpen(false)} className="block rounded-xl px-3 py-2.5 hover:bg-surface">
                <p className="text-[14px]">{n.text}</p>
              </Link>
            ))}
          </div>
        )}
      </div>

      <button type="button" onClick={() => askAssistant()} className="btn-soft !px-4 !py-3">
        <Sparkles size={18} />
        <span className="hidden sm:inline">Demander à l’IA</span>
      </button>
    </header>
  )
}
