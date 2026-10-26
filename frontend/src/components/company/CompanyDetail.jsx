import { Bookmark, Briefcase, Building2, ExternalLink, FileText, Globe, MapPin, Phone, Sparkles, Star } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api'
import { useStore } from '../../store/useStore'
import CompanyLogo from '../ui/CompanyLogo'
import ApplyModal from './ApplyModal'

// Fiche entreprise complète (panneau de droite de la recherche + page entreprise).
export default function CompanyDetail({ id }) {
  const { favorites, toggleFavorite, addToTracking, updateTracking, meta, openCompany, askAssistant, tracking } = useStore()
  const [c, setC] = useState(null)
  const [apply, setApply] = useState(false)
  const t = tracking.find((x) => x.id === id)

  useEffect(() => {
    let live = true
    api.company(id).then((r) => live && setC(r)).catch(() => live && setC(null))
    return () => {
      live = false
    }
  }, [id, tracking.length, t?.statut])

  if (!c || c.id !== id) return <div className="p-6 text-[14px] text-muted">Chargement…</div>
  const fav = favorites.includes(id)
  const R = 34
  const circ = 2 * Math.PI * R
  const info = [
    { label: 'Secteur', value: c.secteur, icon: Briefcase },
    { label: 'Quartier', value: c.quartier, icon: MapPin },
    { label: 'Note Google', value: c.note != null ? `${c.note} / 5` : 'Non communiquée', icon: Star },
    { label: 'Avis', value: c.nb_avis ?? 'Non communiqué', icon: Building2 },
  ]
  return (
    <div>
      <div className="p-6">
        <div className="flex items-start gap-4">
          <CompanyLogo company={c} size="xl" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap gap-2">
              <span className="demo-pill">Google Maps</span>
              <span className="rounded-md bg-primary-soft px-2.5 py-1 text-[11px] font-semibold text-primary">Priorité {c.priorite} · score {c.score}</span>
              {t && <span className="rounded-md bg-success-soft px-2.5 py-1 text-[11px] font-semibold text-success">{t.statut}</span>}
            </div>
            <h2 className="mt-1.5 text-[26px] font-normal leading-tight">{c.short}</h2>
            {c.short !== c.name && <p className="mt-1 text-[12px] text-faint">{c.name}</p>}
          </div>
          <button onClick={() => toggleFavorite(id)} aria-label={fav ? 'Retirer des favoris' : 'Ajouter aux favoris'} className="rounded-lg p-1.5 text-primary hover:bg-surface">
            <Bookmark size={22} fill={fav ? 'currentColor' : 'none'} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 border-y border-line 2xl:grid-cols-4">
        {info.map((i) => (
          <div key={i.label} className="px-5 py-4 text-center 2xl:border-r 2xl:border-line 2xl:last:border-r-0">
            <p className="text-[12px] text-muted">{i.label}</p>
            <i.icon size={20} className="mx-auto my-2 text-primary" />
            <p className="text-[13px] font-semibold">{i.value}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3 p-6">
        <button onClick={() => setApply(true)} className="btn-primary !px-6 !py-3.5">Préparer ma candidature</button>
        {!t && <button onClick={() => addToTracking(id)} className="btn-outline !py-3.5">Ajouter au suivi</button>}
        <button onClick={() => navigate(`/cv-studio?company=${id}`)} className="btn-outline !py-3.5"><FileText size={17} /> CV + e-mail</button>
        <button onClick={() => askAssistant(id)} className="btn-outline !py-3.5"><Sparkles size={17} /> Demander à l’IA</button>
      </div>

      {t && (
        <div className="mx-6 mb-2 flex flex-wrap items-center gap-3 rounded-2xl border border-line p-4">
          <span className="text-[13px] font-semibold">Statut du suivi</span>
          <select value={t.statut} onChange={(e) => updateTracking(t.id, { statut: e.target.value }, 'Statut mis à jour')} className="rounded-lg border border-line bg-white px-2 py-1.5 text-[13px]" aria-label="Statut du suivi">
            {meta.statuts.map((s) => <option key={s}>{s}</option>)}
          </select>
          {t.date_relance && <span className="text-[12px] text-muted">Relance prévue : {t.date_relance}</span>}
        </div>
      )}

      <div className="mx-6 mt-3 flex items-center gap-5 rounded-2xl border border-line bg-primary-soft/40 p-5">
        {c.match != null ? (
          <>
            <div className="relative h-[84px] w-[84px] shrink-0">
              <svg viewBox="0 0 84 84" className="-rotate-90">
                <circle cx="42" cy="42" r={R} fill="none" stroke="#e4e9f1" strokeWidth="6" />
                <circle cx="42" cy="42" r={R} fill="none" stroke="#1f8a5b" strokeWidth="6" strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - c.match / 100)} />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[20px] font-semibold text-success">{c.match}<span className="text-[11px]">%</span></span>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-primary">Compatibilité avec votre profil</p>
              <p className="mt-1 text-[14px]"><strong>En phase :</strong> {c.match_skills.join(', ') || 'aucune'}</p>
              <p className="text-[14px]"><strong>À développer :</strong> {c.missing_skills.join(', ') || 'rien d’identifié'}</p>
              <p className="mt-1 text-[12px] text-muted">Estimation par mots-clés (compétences du profil ↔ secteur), pas une probabilité d’embauche.</p>
            </div>
          </>
        ) : (
          <p className="text-[13px] text-muted">Renseignez vos compétences dans <button className="font-semibold text-primary" onClick={() => navigate('/profil')}>votre profil</button> pour estimer la compatibilité.</p>
        )}
      </div>

      <div className="space-y-6 p-6">
        <section>
          <h3 className="mb-2 text-[18px] font-medium">Coordonnées</h3>
          <ul className="space-y-2 text-[14px] text-muted">
            <li className="flex gap-2"><MapPin size={17} className="mt-0.5 shrink-0 text-primary" />{c.adresse || 'Non communiquée'}{c.distance_km != null && <strong className="ml-1 text-ink">· {c.distance_km} km de chez vous{c.coord_exacte ? '' : ' (approx.)'}</strong>}</li>
            <li className="flex gap-2"><Phone size={17} className="mt-0.5 shrink-0 text-primary" />{c.telephone ? <a className="text-primary hover:underline" href={`tel:${c.telephone}`}>{c.telephone}</a> : 'Non communiqué'}</li>
            <li className="flex gap-2"><Globe size={17} className="mt-0.5 shrink-0 text-primary" />{c.site_web ? <a className="break-all text-primary hover:underline" href={c.site_web} target="_blank" rel="noreferrer">{c.site_web}</a> : 'Pas de site web'}</li>
            {c.lien_maps && <li className="flex gap-2"><ExternalLink size={17} className="mt-0.5 shrink-0 text-primary" /><a className="text-primary hover:underline" href={c.lien_maps} target="_blank" rel="noreferrer">Ouvrir dans Google Maps</a></li>}
          </ul>
        </section>
        <section>
          <h3 className="mb-2 text-[18px] font-medium">À propos de cette entreprise</h3>
          <p className="text-[14px] leading-relaxed text-muted">
            Entreprise du secteur « {c.secteur} » à {c.ville}{c.quartier !== 'Non précisé' ? ` (${c.quartier})` : ''}, trouvée via Google Maps
            {c.requetes ? ` (recherches : ${c.requetes})` : ''}. Aucune offre de stage publiée n’est connue : une candidature spontanée est recommandée.
          </p>
        </section>
        {c.similar?.length > 0 && (
          <section>
            <h3 className="mb-2 text-[18px] font-medium">Entreprises similaires</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {c.similar.map((s) => (
                <button key={s.id} onClick={() => openCompany(s.id)} className="flex items-center gap-3 rounded-xl border border-line p-3 text-left hover:shadow-pop">
                  <CompanyLogo company={s} size="sm" />
                  <span className="min-w-0"><span className="block truncate text-[14px] font-medium">{s.short}</span><span className="text-[12px] text-muted">{s.quartier} · score {s.score}</span></span>
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
      {apply && <ApplyModal company={c} onClose={() => setApply(false)} />}
    </div>
  )
}
