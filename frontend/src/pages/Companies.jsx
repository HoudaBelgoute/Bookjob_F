import { ArrowRight, Bookmark, Search, Star } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import CompanyLogo from '../components/ui/CompanyLogo'
import { useStore } from '../store/useStore'

export default function Companies() {
  const { meta, favorites, toggleFavorite, openCompany } = useStore()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [applied, setApplied] = useState('')
  const [secteur, setSecteur] = useState('')
  const [shown, setShown] = useState(24)
  const [res, setRes] = useState({ total: 0, items: [] })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.companies({ q: applied, secteur: secteur ? [secteur] : [], sort: 'nom', limit: 500 }).then(setRes).finally(() => setLoading(false))
    setShown(24)
  }, [applied, secteur])

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-8 md:px-8">
      <p className="eyebrow">Annuaire</p>
      <h1 className="page-title mt-3">Découvrez les entreprises</h1>
      <p className="mt-3 text-[16px] text-muted">{meta.total_entreprises} entreprises de Marrakech (Google Maps). Suivez celles qui vous intéressent.</p>

      <form onSubmit={(e) => { e.preventDefault(); setApplied(q) }} className="card mt-8 flex max-w-[1050px] flex-wrap items-center gap-3 p-2.5 pl-5">
        <Search size={20} className="text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher une entreprise ou un mot-clé" aria-label="Rechercher une entreprise" className="min-w-[200px] flex-1 bg-transparent py-2 text-[15px] outline-none placeholder:text-faint" />
        <select value={secteur} onChange={(e) => setSecteur(e.target.value)} aria-label="Secteur" className="rounded-xl border border-line bg-white px-3 py-2.5 text-[14px]">
          <option value="">Tous les secteurs</option>
          {meta.secteurs.map((s) => <option key={s}>{s}</option>)}
        </select>
        <button type="submit" className="btn-primary !px-6 !py-3">Rechercher</button>
      </form>

      {loading ? (
        <p className="mt-10 text-muted">Chargement…</p>
      ) : res.items.length === 0 ? (
        <p className="mt-10 text-muted">Aucune entreprise ne correspond à votre recherche.</p>
      ) : (
        <>
          <p className="mt-6 text-[14px] text-muted"><strong className="text-ink">{res.total}</strong> entreprises</p>
          <div className="mt-3 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {res.items.slice(0, shown).map((c) => (
              <article key={c.id} className="card flex flex-col p-6">
                <div className="flex items-start justify-between">
                  <CompanyLogo company={c} size="xl" />
                  <button onClick={() => toggleFavorite(c.id)} aria-label="Suivre l’entreprise" className="rounded-lg p-1.5 text-primary hover:bg-surface">
                    <Bookmark size={22} fill={favorites.includes(c.id) ? 'currentColor' : 'none'} />
                  </button>
                </div>
                <span className="demo-pill mt-5 w-fit border border-[#efdfaa]">Google Maps</span>
                <h2 className="mt-3 text-[20px] font-normal leading-snug">{c.short}</h2>
                <p className="mt-1 text-[13px] text-primary">{c.secteur} · {c.quartier}</p>
                <p className="mt-1.5 flex items-center gap-1.5 text-[13px] text-muted">
                  <Star size={14} /> {c.note != null ? `${c.note} (${c.nb_avis ?? 0} avis)` : 'Non noté'} · {c.site_web ? 'Site web' : 'Sans site web'}
                </p>
                <div className="mt-auto flex items-center justify-between border-t border-line pt-5">
                  <span className="text-[12px] text-muted">Score <strong className="text-ink">{c.score}</strong> · Priorité {c.priorite}</span>
                  <button onClick={() => { openCompany(c.id); navigate('/rechercher') }} className="flex items-center gap-2 text-[15px] font-semibold text-primary">
                    Voir l’entreprise <ArrowRight size={17} />
                  </button>
                </div>
              </article>
            ))}
          </div>
          {shown < res.items.length && <button className="btn-outline mx-auto mt-6 block" onClick={() => setShown(shown + 24)}>Afficher plus</button>}
        </>
      )}
    </div>
  )
}
