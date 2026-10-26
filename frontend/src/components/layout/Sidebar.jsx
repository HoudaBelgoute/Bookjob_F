import clsx from 'clsx'
import {
  ArrowRight,
  Bookmark,
  BarChart3,
  Briefcase,
  Building2,
  FileText,
  GraduationCap,
  LayoutGrid,
  LogOut,
  MapPin,
  MoreHorizontal,
  Search,
  Settings,
  UserRoundPen,
} from 'lucide-react'

import { useEffect, useRef, useState } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { useStore } from '../../store/useStore'
import { useAuth } from '../AuthGate'
import UserAvatar from '../ui/UserAvatar'

const NAV = [
  { to: '/', label: 'Tableau de bord', icon: LayoutGrid, end: true },
  { to: '/rechercher', label: 'Rechercher', icon: Search },
  { to: '/candidatures', label: 'Mes candidatures', icon: Briefcase, badge: true },
  { to: '/favoris', label: 'Favoris', icon: Bookmark },
  { to: '/entreprises', label: 'Entreprises', icon: Building2 },
  { to: '/carte', label: 'Carte & distance', icon: MapPin },
  { to: '/cv-studio', label: 'CV Studio', icon: FileText },
  { to: '/statistiques', label: 'Statistiques', icon: BarChart3 },
  { to: '/formations', label: 'Formations', icon: GraduationCap },
]

const ACTIVE_STATUSES = new Set(['Candidature envoyée', 'En cours de traitement', 'Entretien programmé'])

function Item({ to, label, icon: Icon, end, badge, onNavigate }) {
  const inProgress = useStore((s) => s.tracking.filter((a) => ACTIVE_STATUSES.has(a.statut)).length)
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        clsx(
          'relative flex items-center gap-3 rounded-xl px-4 py-3 text-[15px] transition-colors',
          isActive ? 'bg-navy-700 font-medium text-white' : 'text-[#c9d6ea] hover:bg-navy-800 hover:text-white',
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && <span className="absolute -left-4 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r bg-[#5aa0ff]" />}
          <Icon size={20} strokeWidth={1.8} />
          <span className="flex-1">{label}</span>
          {badge && inProgress > 0 && (
            <span className="flex h-[22px] min-w-[22px] items-center justify-center rounded-full bg-primary px-1.5 text-[12px] font-semibold text-white">
              {inProgress}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

export default function Sidebar({ onNavigate }) {
  const { profile, completion, avatarUrl } = useStore()
  const { required, signOut: authSignOut } = useAuth()
  const pct = completion.percent
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const accountMenuRef = useRef(null)

  useEffect(() => {
    const closeOnOutsideClick = (event) => {
      if (accountMenuRef.current && !accountMenuRef.current.contains(event.target)) {
        setAccountMenuOpen(false)
      }
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setAccountMenuOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [])

  const signOut = async () => {
    if (!window.confirm('Se déconnecter de BookJob ? Tes données et ton compte Gmail resteront associés à ton compte.')) return
    try {
      await authSignOut()
    } catch (error) {
      window.alert(error.message)
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-navy-900 text-white">
      <Link to="/" onClick={onNavigate} className="flex items-center gap-3 border-b border-white/10 px-6 py-4">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary">
          <Briefcase size={20} />
        </span>
        <span className="text-[24px] font-bold tracking-tight">
          Book<span className="text-[#5aa0ff]">Job</span>
        </span>
      </Link>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <p className="px-6 pb-3 pt-7 text-[12px] font-semibold uppercase tracking-[0.16em] text-[#9fb2d0]">
          Espace candidat
        </p>

        <nav className="space-y-1 px-4" aria-label="Navigation principale">
          {NAV.map((n) => (
            <Item key={n.to} {...n} onNavigate={onNavigate} />
          ))}
        </nav>

        {pct < 100 && (
          <div className="mx-4 mt-6 rounded-2xl border border-white/10 bg-navy-800/60 p-4">
            <div className="flex items-center justify-between text-[14px]">
              <span className="font-medium">Profil complété</span>
              <span className="font-semibold">{pct}%</span>
            </div>
            <div className="mt-3 h-1.5 rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gold" style={{ width: `${pct}%` }} />
            </div>
            <Link
              to="/profil"
              onClick={onNavigate}
              className="mt-4 flex items-center gap-2 text-[14px] font-medium text-[#8fc0ff] hover:text-white"
            >
              Compléter mon profil <ArrowRight size={15} />
            </Link>
          </div>
        )}

        <div className="mt-4 border-t border-white/10">
          <NavLink
            to="/parametres"
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-8 py-4 text-[15px] hover:text-white',
                isActive ? 'text-white' : 'text-[#c9d6ea]',
              )
            }
          >
            <Settings size={20} strokeWidth={1.8} /> Paramètres
          </NavLink>
          <div ref={accountMenuRef} className="relative flex items-center gap-2 border-t border-white/10 px-4 py-3">
            <Link
              to="/profil"
              onClick={onNavigate}
              className="flex min-w-0 flex-1 items-center gap-3 rounded-lg px-2 py-1 hover:bg-navy-800"
            >
              <UserAvatar name={profile.nom} url={avatarUrl} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[14px] font-semibold">{profile.nom || 'Mon profil'}</span>
                <span className="block truncate text-[12px] text-[#9fb2d0]">{profile.titre || 'Compléter le profil'}</span>
              </span>
            </Link>
            <button
              type="button"
              onClick={() => setAccountMenuOpen((open) => !open)}
              aria-label="Actions du profil"
              aria-haspopup="menu"
              aria-expanded={accountMenuOpen}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#9fb2d0] hover:bg-navy-800 hover:text-white"
            >
              <MoreHorizontal size={20} />
            </button>
            {accountMenuOpen && (
              <div role="menu" className="absolute bottom-[calc(100%-0.25rem)] right-4 z-50 w-56 rounded-xl border border-white/10 bg-navy-800 p-1.5 shadow-pop">
                <Link
                  role="menuitem"
                  to="/profil"
                  onClick={() => {
                    setAccountMenuOpen(false)
                    onNavigate?.()
                  }}
                  className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-[14px] text-white hover:bg-navy-700"
                >
                  <UserRoundPen size={17} />
                  Modifier mon profil
                </Link>
                {required && (
                  <button
                    role="menuitem"
                    type="button"
                    onClick={signOut}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-[14px] text-white hover:bg-navy-700"
                  >
                    <LogOut size={17} />
                    Changer d’utilisateur / sortir
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
