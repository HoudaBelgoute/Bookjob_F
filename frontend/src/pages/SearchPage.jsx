import clsx from 'clsx'
import { Bell, Bookmark, Briefcase, Check, ChevronRight, MapPin, Search, Star, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import CompanyDetail from '../components/company/CompanyDetail'
import ApplyModal from '../components/company/ApplyModal'
import CompanyLogo from '../components/ui/CompanyLogo'
import { useStore } from '../store/useStore'

const PAGE = 30
const DEFAULTS = { q: '', secteur: [], quartier: [], priorite: ['A', 'B'], score_min: 60, note_min: 0, avec_site: false, suivi: '', sort: 'score', dmax: '' }

function Checkbox({ checked, onChange, label, count }) {
  return (
    <label className="flex cursor-pointer items-center gap-3 py-1.5 text-[14px] text-muted">
      <span className={clsx('flex h-[18px] w-[18px] items-center justify-center rounded-md border', checked ? 'border-primary bg-primary text-white' : 'border-[#c5cedc] bg-white')}>
        {checked && <Check size={12} strokeWidth={3} />}
      </span>
      <input type="checkbox" className="sr-only" checked={checked} onChange={onChange} />
      <span className="flex-1">{label}</span>
      {count != null && <span className="text-[12px] text-faint">{count}</span>}
    </label>
  )
}

const toggle = (list, v) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

export default function SearchPage() {
  const { meta, favorites, toggleFavorite, activeCompanyId, openCompany, addAlert, home, profile } = useStore()
  const [params] = useSearchParams()
  const [draftQ, setDraftQ] = useState(params.get('q') || '')
  const [f, setF] = useState({ ...DEFAULTS, q: params.get('q') || '' })
  const [res, setRes] = useState({ total: 0, items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [shown, setShown] = useState(PAGE)
  const [applyFor, setApplyFor] = useState(null)

  useEffect(() => {
    let live = true
    setLoading(true)
    api
      .companies({ ...f, dmax: f.dmax || undefined, limit: 500, score_min: f.score_min || undefined, note_min: f.note_min || undefined })
      .then((r) => live && (setRes(r), setError(''), setShown(PAGE)))
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
  }, [f, home])

  const selected = useMemo(() => res.items.find((c) => c.id === activeCompanyId) || res.items[0], [res.items, activeCompanyId])
  const set = (patch) => setF((p) => ({ ...p, ...patch }))
  const reset = () => { setF({ ...DEFAULTS }); setDraftQ('') }
  const chips = [
    f.q && { k: 'q', label: `« ${f.q} »`, clear: () => { set({ q: '' }); setDraftQ('') } },
    ...f.secteur.map((s) => ({ k: `s${s}`, label: s, clear: () => set({ secteur: f.secteur.filter((x) => x !== s) }) })),
    ...f.quartier.map((s) => ({ k: `q${s}`, label: s, clear: () => set({ quartier: f.quartier.filter((x) => x !== s) }) })),
  ].filter(Boolean)
  const sel = 'w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] outline-none'

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-8 md:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Recherche d’opportunités</p>
          <h1 className="page-title mt-3">Trouvez votre prochain stage</h1>
          <p className="mt-3 text-[16px] text-muted">{meta.total_entreprises} entreprises de Marrakech issues de Google Maps, classées par score.</p>
        </div>
        <button className="btn-soft !px-5 !py-3.5" onClick={() => addAlert(f.q || 'Toutes les entreprises')}>
          <Bell size={18} /> Enregistrer cette recherche
        </button>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); set({ q: draftQ.trim() }) }} className="card mt-8 grid items-stretch gap-2 p-2.5 md:grid-cols-[1.6fr_1fr_1fr_auto]">
        <label className="flex items-center gap-3 px-4 py-2 md:border-r md:border-line">
          <Search size={20} className="text-primary" />
          <span className="flex-1">
            <span className="block text-[11px] font-semibold uppercase tracking-widest text-muted">Quoi ?</span>
            <input value={draftQ} onChange={(e) => setDraftQ(e.target.value)} placeholder="Nom d’entreprise, secteur, mot-clé" className="w-full bg-transparent text-[15px] outline-none placeholder:text-faint" />
          </span>
        </label>
        <label className="flex items-center gap-3 px-4 py-2 md:border-r md:border-line">
          <Briefcase size={20} className="text-primary" />
          <span className="flex-1">
            <span className="block text-[11px] font-semibold uppercase tracking-widest text-muted">Secteur</span>
            <select value={f.secteur[0] || ''} onChange={(e) => set({ secteur: e.target.value ? [e.target.value] : [] })} className="w-full bg-transparent text-[15px] outline-none">
              <option value="">Tous</option>
              {meta.secteurs.map((s) => <option key={s}>{s}</option>)}
            </select>
          </span>
        </label>
        <label className="flex items-center gap-3 px-4 py-2">
          <MapPin size={20} className="text-primary" />
          <span className="flex-1">
            <span className="block text-[11px] font-semibold uppercase tracking-widest text-muted">Quartier</span>
            <select value={f.quartier[0] || ''} onChange={(e) => set({ quartier: e.target.value ? [e.target.value] : [] })} className="w-full bg-transparent text-[15px] outline-none">
              <option value="">Tous</option>
              {meta.quartiers.map((s) => <option key={s}>{s}</option>)}
            </select>
          </span>
        </label>
        <button type="submit" className="btn-primary !rounded-xl !px-8 !py-4"><Search size={18} /> Rechercher</button>
      </form>

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        {chips.map((c) => (
          <span key={c.k} className="inline-flex items-center gap-2 rounded-lg bg-primary-soft px-3 py-1.5 text-[13px] font-medium text-primary">
            {c.label}
            <button onClick={c.clear} aria-label={`Retirer ${c.label}`}><X size={13} /></button>
          </span>
        ))}
        <button onClick={reset} className="text-[14px] text-muted underline hover:text-ink">Effacer tout</button>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,500px)_minmax(0,1fr)]">
        <aside className="card self-start p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-[18px] font-semibold">Filtres</h2>
            <button onClick={reset} className="text-[13px] font-medium text-primary">Réinitialiser</button>
          </div>

          <h3 className="mb-1 mt-5 text-[14px] font-semibold">Priorité</h3>
          {meta.priorites.map((p) => (
            <Checkbox key={p} label={`Priorité ${p}`} checked={f.priorite.includes(p)} onChange={() => set({ priorite: toggle(f.priorite, p) })} />
          ))}

          <div className="mt-3 border-t border-line pt-4">
            <h3 className="mb-2 flex justify-between text-[14px] font-semibold">Score minimum <span className="text-primary">{f.score_min}</span></h3>
            <input type="range" min="0" max="100" value={f.score_min} onChange={(e) => set({ score_min: Number(e.target.value) })} className="w-full accent-primary" aria-label="Score minimum" />
          </div>

          <div className="mt-3 border-t border-line pt-4">
            <h3 className="mb-2 flex justify-between text-[14px] font-semibold">Note Google min. <span className="text-primary">{f.note_min || '—'}</span></h3>
            <input type="range" min="0" max="5" step="0.5" value={f.note_min} onChange={(e) => set({ note_min: Number(e.target.value) })} className="w-full accent-primary" aria-label="Note minimum" />
            <Checkbox label="Avec site web" checked={f.avec_site} onChange={() => set({ avec_site: !f.avec_site })} />
          </div>

          <div className="mt-3 border-t border-line pt-4">
            <h3 className="mb-2 text-[14px] font-semibold">Suivi</h3>
            <select value={f.suivi} onChange={(e) => set({ suivi: e.target.value })} className={sel} aria-label="Suivi">
              <option value="">Toutes</option>
              <option value="non">Pas encore dans mon suivi</option>
              <option value="oui">Déjà dans mon suivi</option>
            </select>
          </div>

          <div className="mt-3 border-t border-line pt-4">
            <h3 className="mb-2 text-[14px] font-semibold">Secteurs</h3>
            {meta.secteurs.map((s) => (
              <Checkbox key={s} label={s} count={meta.secteur_counts[s]} checked={f.secteur.includes(s)} onChange={() => set({ secteur: toggle(f.secteur, s) })} />
            ))}
          </div>

          <div className="mt-3 border-t border-line pt-4">
            <h3 className="mb-2 text-[14px] font-semibold">Distance maximale</h3>
            {home ? (
              <label className="flex items-center gap-2 text-[13px] text-muted">
                <input type="number" min="0" step="0.5" value={f.dmax} onChange={(e) => set({ dmax: e.target.value })} placeholder="∞" className="w-20 rounded-lg border border-line px-2 py-1.5" aria-label="Distance maximale en km" /> km de chez moi
              </label>
            ) : (
              <p className="text-[12px] text-muted">Définissez votre localisation dans l’onglet « Carte & distance » pour filtrer par distance.</p>
            )}
          </div>
        </aside>

        <section aria-label="Résultats">
          <div className="mb-3 flex items-center justify-between text-[14px] text-muted">
            <p><strong className="text-ink">{res.total} entreprise{res.total > 1 ? 's' : ''}</strong> à Marrakech</p>
            <label className="flex items-center gap-2">
              Trier par
              <select value={f.sort} onChange={(e) => set({ sort: e.target.value })} className="bg-transparent font-semibold text-ink outline-none">
                <option value="score">Score</option>
                <option value="match">Meilleur matching avec mon profil</option>
                <option value="distance" disabled={!home}>Distance</option>
                <option value="note">Note Google</option>
                <option value="avis">Nombre d’avis</option>
                <option value="nom">Nom (A–Z)</option>
              </select>
            </label>
          </div>

          {error ? (
            <div className="card p-8 text-center"><p className="font-medium">Erreur de chargement</p><p className="mt-1 text-[14px] text-muted">{error}</p></div>
          ) : loading && res.items.length === 0 ? (
            <div className="space-y-3">{[0, 1, 2].map((i) => <div key={i} className="card h-36 animate-pulse bg-chip" />)}</div>
          ) : res.items.length === 0 ? (
            <div className="card p-8 text-center">
              <p className="text-[16px] font-medium">Aucune entreprise ne correspond.</p>
              <p className="mt-1 text-[14px] text-muted">Baissez le score minimum, ajoutez la priorité C ou effacez les filtres.</p>
              <button onClick={reset} className="btn-outline mt-4">Effacer tout</button>
            </div>
          ) : (
            <div className="space-y-3">
              {res.items.slice(0, shown).map((c) => {
                const isSel = selected?.id === c.id
                const fav = favorites.includes(c.id)
                return (
                  <article key={c.id} onClick={() => openCompany(c.id)} className={clsx('card cursor-pointer p-5 transition-shadow hover:shadow-pop', isSel && '!border-2 !border-primary')}>
                    <div className="flex items-start gap-4">
                      <CompanyLogo company={c} size="lg" />
                      <div className="min-w-0 flex-1">
                        <h3 className="text-[17px] font-medium leading-snug">{c.short}</h3>
                        <p className="mt-0.5 text-[14px] text-muted">{c.secteur}</p>
                      </div>
                      <button onClick={(e) => { e.stopPropagation(); toggleFavorite(c.id) }} aria-label={fav ? 'Retirer des favoris' : 'Ajouter aux favoris'} className="rounded-lg p-1.5 text-primary hover:bg-surface">
                        <Bookmark size={20} fill={fav ? 'currentColor' : 'none'} />
                      </button>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-muted">
                      <span className="flex items-center gap-1.5"><MapPin size={15} />{c.quartier}{c.distance_km != null && ` · ${c.distance_km} km`}</span>
                      <span className="flex items-center gap-1.5"><Star size={15} />{c.note != null ? `${c.note} (${c.nb_avis ?? 0} avis)` : 'Pas de note'}</span>
                      {c.statut && <span className="rounded-md bg-success-soft px-2 py-0.5 text-[12px] font-semibold text-success">{c.statut}</span>}
                    </div>
                    <div className="mt-4 flex items-center justify-between border-t border-line pt-3">
                      <span className="flex items-center gap-2 text-[13px] text-muted">
                        <span className="rounded-md bg-primary-soft px-2 py-1 text-[12px] font-semibold text-primary">Score {c.score}</span>
                        <span className="tag">Priorité {c.priorite}</span>
                        {c.match != null && <span className={clsx('rounded-md px-2 py-1 text-[12px] font-semibold', c.match >= 70 ? 'bg-success-soft text-success' : 'bg-gold-soft text-gold-ink')} title="Compatibilité estimée avec votre profil">{c.match}% profil</span>}
                      </span>
                      <div className="flex items-center gap-3">
                        <button onClick={(e) => { e.stopPropagation(); setApplyFor(c) }} className="btn-primary !px-3 !py-2 text-[12px]">Postuler</button>
                        <span className="flex items-center gap-1 text-[14px] font-medium text-primary">Détails <ChevronRight size={16} /></span>
                      </div>
                    </div>
                  </article>
                )
              })}
              {shown < res.items.length && (
                <button className="btn-outline w-full" onClick={() => setShown(shown + PAGE)}>Afficher plus ({res.items.length - shown} restantes)</button>
              )}
            </div>
          )}
        </section>

        {selected && (
          <aside className="card self-start overflow-hidden lg:col-span-2 xl:sticky xl:top-24 xl:col-span-1 xl:max-h-[calc(100vh-7rem)] xl:overflow-y-auto">
            <CompanyDetail id={selected.id} />
          </aside>
        )}
        {applyFor && <ApplyModal company={applyFor} onClose={() => setApplyFor(null)} />}
      </div>
      {!profile.competences && <p className="mt-4 text-[12px] text-muted">Astuce : renseignez vos compétences dans le profil pour activer le tri « Meilleur matching ».</p>}
    </div>
  )
}
