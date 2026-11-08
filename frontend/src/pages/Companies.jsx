import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import CompanyCard from '../components/company/CompanyCard'
import { useStore } from '../store/useStore'

export default function Companies() {
  const { meta, favorites, toggleFavorite } = useStore()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [applied, setApplied] = useState('')
  const [secteur, setSecteur] = useState('')
  const [shown, setShown] = useState(24)
  const [res, setRes] = useState({ total: 0, items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    api.companies({ q: applied, secteur: secteur ? [secteur] : [], sort: 'nom', limit: 500 })
      .then((result) => {
        if (active) setRes(result)
      })
      .catch((err) => {
        if (active) setError(err.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    setShown(24)
    return () => {
      active = false
    }
  }, [applied, secteur])

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-8 md:px-8">
      <p className="eyebrow">Annuaire</p>
      <h1 className="page-title mt-3">Découvrez les entreprises</h1>
      <p className="mt-3 text-[16px] text-muted">{meta.total_entreprises} entreprises de Marrakech (Google Maps). Suivez celles qui vous intéressent.</p>

      <form onSubmit={(e) => { e.preventDefault(); setApplied(q) }} className="card mt-8 flex max-w-[1050px] flex-wrap items-center gap-3 p-2.5 pl-5">
        <Search size={20} className="text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher une entreprise ou un mot-clé" aria-label="Rechercher une entreprise" className="min-w-[200px] flex-1 bg-transparent py-2 text-[15px] outline-none placeholder:text-faint" />
        <select value={secteur} onChange={(e) => setSecteur(e.target.value)} aria-label="Secteur" className="rounded-xl border border-line bg-card px-3 py-2.5 text-[14px] text-ink">
          <option value="">Tous les secteurs</option>
          {meta.secteurs.map((s) => <option key={s}>{s}</option>)}
        </select>
        <button type="submit" className="btn-primary !px-6 !py-3">Rechercher</button>
      </form>

      {loading ? (
        <p className="mt-10 text-muted">Chargement…</p>
      ) : error ? (
        <p role="alert" className="mt-10 text-red-600">{error}</p>
      ) : res.items.length === 0 ? (
        <p className="mt-10 text-muted">Aucune entreprise ne correspond à votre recherche.</p>
      ) : (
        <>
          <p className="mt-6 text-[14px] text-muted"><strong className="text-ink">{res.total}</strong> entreprises</p>
          <div className="mt-3 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {res.items.slice(0, shown).map((c) => (
              <CompanyCard
                key={c.id}
                company={c}
                favorite={favorites.includes(c.id)}
                onFavorite={() => toggleFavorite(c.id)}
                onOpen={() => navigate(`/entreprises/${encodeURIComponent(c.id)}`)}
              />
            ))}
          </div>
          {shown < res.items.length && <button className="btn-outline mx-auto mt-6 block" onClick={() => setShown(shown + 24)}>Afficher plus</button>}
        </>
      )}
    </div>
  )
}
