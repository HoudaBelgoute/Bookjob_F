import { Bell, Menu, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { useStore } from '../../store/useStore'

export default function Topbar({ onMenu }) {
  const askAssistant = useStore((s) => s.askAssistant)
  const [open, setOpen] = useState(false)
  const [notifs, setNotifs] = useState([])
  useEffect(() => {
    api.notifications().then((r) => setNotifs(r.items)).catch(() => setNotifs([]))
  }, [open])
  const ref = useRef(null)

  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-white px-4 py-3.5 md:px-8">
      <button
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
          onClick={() => setOpen((v) => !v)}
          aria-label="Notifications"
          aria-expanded={open}
          className="relative flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-white hover:bg-surface"
        >
          <Bell size={20} />
          {notifs.length > 0 && <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-red-500" />}
        </button>
        {open && (
          <div className="absolute right-0 top-14 w-80 rounded-2xl border border-line bg-white p-2 shadow-pop">
            <p className="px-3 py-2 text-[13px] font-semibold text-muted">Notifications</p>
            {notifs.length === 0 && <p className="px-3 py-3 text-[13px] text-muted">Aucune notification.</p>}
            {notifs.map((n) => (
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
