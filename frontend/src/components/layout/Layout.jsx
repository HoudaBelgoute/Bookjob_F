import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useStore } from '../../store/useStore'
import ChatWidget from '../ChatWidget'
import Toast from '../ui/Toast'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

export default function Layout() {
  const [drawer, setDrawer] = useState(false)
  const { pathname } = useLocation()
  const { ready, error, init } = useStore()

  useEffect(() => {
    init()
  }, [init])

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  if (error)
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="card max-w-md p-8 text-center">
          <h1 className="text-[22px] font-medium">Serveur injoignable</h1>
          <p className="mt-2 text-[14px] text-muted">{error}</p>
          <p className="mt-2 text-[13px] text-muted">
            Lancez le backend (<code>start.bat</code> ou <code>./start.sh</code>) puis rechargez la page.
          </p>
          <button className="btn-primary mt-5" onClick={() => location.reload()}>
            Recharger
          </button>
        </div>
      </div>
    )
  if (!ready) return <div className="p-10 text-muted">Chargement des données…</div>

  return (
    <div className="min-h-full lg:pl-[288px]">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[288px] lg:block">
        <Sidebar />
      </aside>

      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-navy-900/50" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 w-[288px] max-w-[85%]">
            <Sidebar onNavigate={() => setDrawer(false)} />
            <button
              onClick={() => setDrawer(false)}
              aria-label="Fermer le menu"
              className="absolute right-3 top-4 rounded-lg p-1.5 text-white/80 hover:bg-white/10"
            >
              <X size={20} />
            </button>
          </div>
        </div>
      )}

      <div className="flex min-h-screen flex-col">
        <Topbar onMenu={() => setDrawer(true)} />
        <main className="flex-1">
          <Outlet />
        </main>
      </div>

      <ChatWidget />
      <Toast />
    </div>
  )
}
