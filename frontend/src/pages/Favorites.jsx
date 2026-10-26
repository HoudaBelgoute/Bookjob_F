import { Bookmark } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import ApplyModal from '../components/company/ApplyModal'
import CompanyLogo from '../components/ui/CompanyLogo'
import { useStore } from '../store/useStore'

export default function Favorites() {
  const { favorites, toggleFavorite, openCompany } = useStore()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [apply, setApply] = useState(null)

  useEffect(() => {
    if (!favorites.length) return setItems([])
    api.companies({ favorites_only: true, sort: 'score', limit: 500 }).then((r) => setItems(r.items))
  }, [favorites])

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-8">
      <p className="eyebrow">Enregistrées</p>
      <h1 className="page-title mt-3">Favoris</h1>
      <p className="mt-3 text-[16px] text-muted">Les entreprises que vous avez mises de côté.</p>

      {items.length === 0 ? (
        <div className="card mt-8 p-10 text-center">
          <p className="text-[16px] font-medium">Aucune entreprise en favori.</p>
          <p className="mt-1 text-[14px] text-muted">Utilisez l’icône de signet sur une entreprise pour l’enregistrer ici.</p>
          <Link to="/rechercher" className="btn-primary mt-5">Rechercher des entreprises</Link>
        </div>
      ) : (
        <div className="mt-8 space-y-4">
          {items.map((c) => (
            <article key={c.id} className="card flex flex-wrap items-center gap-4 p-5">
              <CompanyLogo company={c} size="lg" />
              <div className="min-w-0 flex-1">
                <h2 className="text-[18px] font-medium">{c.short}</h2>
                <p className="text-[13px] text-muted">{c.secteur} · {c.quartier} · score {c.score}{c.statut ? ` · ${c.statut}` : ''}</p>
              </div>
              <button className="btn-outline" onClick={() => { openCompany(c.id); navigate('/rechercher') }}>Voir la fiche</button>
              <button className="btn-primary !py-2.5" onClick={() => setApply(c)}>Préparer ma candidature</button>
              <button onClick={() => toggleFavorite(c.id)} aria-label="Retirer des favoris" className="rounded-lg p-2 text-primary hover:bg-surface">
                <Bookmark size={22} fill="currentColor" />
              </button>
            </article>
          ))}
        </div>
      )}
      {apply && <ApplyModal company={apply} onClose={() => setApply(null)} />}
    </div>
  )
}
