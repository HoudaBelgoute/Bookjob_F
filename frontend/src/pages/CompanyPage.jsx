import {
  ArrowLeft,
  ArrowUpRight,
  Bookmark,
  Briefcase,
  ExternalLink,
  FileText,
  Globe,
  Mail,
  MessageCircle,
  MapPin,
  Phone,
  Sparkles,
  Star,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import ApplyModal from '../components/company/ApplyModal'
import SitePreview from '../components/company/SitePreview'
import { hostOf } from '../components/company/siteShot'
import CompanyLogo from '../components/ui/CompanyLogo'
import { useStore } from '../store/useStore'
import { buildWhatsAppUrl } from '../utils/whatsapp'

const go = (sectionId) => document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

export default function CompanyPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { favorites, toggleFavorite, addToTracking, askAssistant, tracking } = useStore()
  const [c, setC] = useState(null)
  const [error, setError] = useState('')
  const [apply, setApply] = useState(false)
  const [contactMethod, setContactMethod] = useState('email')
  const [goal, setGoal] = useState('stage')

  useEffect(() => {
    let live = true
    setC(null)
    setError('')
    api.company(id)
      .then((result) => {
        if (live) setC(result)
      })
      .catch((err) => {
        if (live) setError(err.message)
      })
    return () => {
      live = false
    }
  }, [id])

  if (error)
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10">
        <button onClick={() => navigate('/entreprises')} className="flex items-center gap-2 text-[14px] font-semibold text-primary">
          <ArrowLeft size={18} /> Retour aux entreprises
        </button>
        <p role="alert" className="mt-6 text-red-600">Impossible de charger cette entreprise : {error}</p>
      </div>
    )
  if (!c) return <div className="p-10 text-muted">Chargement…</div>

  const fav = favorites.includes(c.id)
  const t = tracking.find((x) => x.id === c.id)
  const goalLabel = goal === 'emploi' ? 'un emploi' : goal === 'spontanee' ? 'une candidature spontanée' : 'un stage ou un PFE'
  const whatsappUrl = buildWhatsAppUrl(
    c.telephone,
    `Bonjour, je souhaite vous contacter au sujet de ${goalLabel} chez ${c.short}. Pourriez-vous m’indiquer la personne à contacter ?`,
  )
  const quartier = c.quartier && c.quartier !== 'Non précisé' ? `, quartier ${c.quartier}` : ''
  const about = [
    `${c.short} est une entreprise du secteur « ${c.secteur} » basée à ${c.ville}${quartier}.`,
    c.note != null ? `Elle est notée ${c.note}/5 sur Google Maps${c.nb_avis ? ` (${c.nb_avis} avis)` : ''}.` : null,
    c.site_web
      ? `Son site officiel (${hostOf(c.site_web)}) présente ses activités et ses coordonnées.`
      : 'Elle n’a pas de site web référencé : un appel ou une visite peut être le meilleur moyen de la contacter.',
  ]
    .filter(Boolean)
    .join(' ')

  const info = [
    { label: 'Secteur', value: c.secteur, icon: Briefcase },
    { label: 'Quartier', value: c.quartier, icon: MapPin },
    { label: 'Note Google', value: c.note != null ? `${c.note} / 5` : 'Non communiquée', icon: Star },
    { label: 'Avis', value: c.nb_avis ?? 'Non communiqué', icon: Sparkles },
  ]

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8 md:px-8">
      <button onClick={() => navigate('/entreprises')} className="group flex items-center gap-2 text-[14px] font-semibold text-primary">
        <ArrowLeft size={18} className="transition-transform group-hover:-translate-x-1" /> Retour aux entreprises
      </button>

      <section className="card relative mt-5 overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-70 [background-image:radial-gradient(var(--line)_1px,transparent_1px)] [background-size:18px_18px]"
        />
        <div className="relative grid gap-10 p-6 md:p-10 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="eyebrow">Fiche entreprise</p>
            <div className="mt-4 flex items-center gap-3">
              <CompanyLogo company={c} size="xl" />
              <span className="text-[14px] font-semibold text-primary">
                {c.secteur}
                {c.quartier && c.quartier !== 'Non précisé' ? ` · ${c.quartier}` : ''}
              </span>
            </div>
            <h1 className="mt-5 text-[34px] font-semibold leading-tight tracking-tight text-ink md:text-[44px]">{c.short}</h1>
            {c.short !== c.name && <p className="mt-1 text-[13px] text-faint">{c.name}</p>}
            {c.adresse && (
              <p className="mt-4 flex items-start gap-2 text-[15px] text-muted">
                <MapPin size={18} className="mt-0.5 shrink-0 text-primary" /> {c.adresse}
              </p>
            )}
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="tag">
                <Star size={12} className="mr-1 inline" /> {c.note != null ? `${c.note}/5` : 'Non noté'}
                {c.nb_avis ? ` · ${c.nb_avis} avis` : ''}
              </span>
              <span className="tag">Priorité {c.priorite} · score {c.score}</span>
              {t && <span className="rounded-lg bg-success-soft px-3 py-1 text-[12px] font-medium text-success">{t.statut}</span>}
            </div>
            <div className="mt-7 flex flex-wrap gap-3">
              <button onClick={() => toggleFavorite(c.id)} className="btn-outline !py-3">
                <Bookmark size={17} fill={fav ? 'currentColor' : 'none'} /> {fav ? 'Dans mon carnet' : 'Garder dans mon carnet'}
              </button>
              <button onClick={() => setApply(true)} className="btn-primary">
                Préparer ma candidature
              </button>
              <button onClick={() => navigate(`/cv-studio?company=${encodeURIComponent(c.id)}`)} className="btn-soft">
                <FileText size={17} /> Lettre de motivation
              </button>
            </div>
          </div>

          <div className="flex items-center justify-center">
            {c.site_web ? (
              <a
                href={c.site_web}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full max-w-[560px] rotate-2 rounded-2xl border border-line bg-card shadow-pop transition duration-500 hover:rotate-0 hover:scale-[1.02]"
              >
                <div className="flex items-center gap-1.5 border-b border-line px-4 py-3">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#e07a8a]" />
                  <span className="h-2.5 w-2.5 rounded-full bg-gold" />
                  <span className="h-2.5 w-2.5 rounded-full bg-success" />
                  <span className="ml-3 text-[10px] font-semibold uppercase tracking-widest text-faint">Aperçu du site</span>
                </div>
                <SitePreview
                  url={c.site_web}
                  height={320}
                  fallback={
                    <div className="flex h-full items-center justify-center bg-primary-soft">
                      <CompanyLogo company={c} size="xl" />
                    </div>
                  }
                />
                <div className="flex items-center justify-between border-t border-line px-4 py-3 text-[13px] text-muted">
                  <span className="flex items-center gap-2">
                    <Globe size={15} /> {hostOf(c.site_web)}
                  </span>
                  <ExternalLink size={15} className="text-primary" />
                </div>
              </a>
            ) : (
              <div className="flex h-[300px] w-full max-w-[560px] items-center justify-center rounded-2xl border border-dashed border-line bg-primary-soft">
                <CompanyLogo company={c} size="xl" />
              </div>
            )}
          </div>
        </div>

        <div className="relative flex flex-wrap gap-3 border-t border-line p-4 md:px-10">
          {[
            ['01', 'L’entreprise', 'entreprise'],
            ['02', 'Les opportunités', 'opportunites'],
            ['03', 'Prendre contact', 'contact'],
          ].map(([n, label, target]) => (
            <button
              key={target}
              onClick={() => go(target)}
              className="group flex items-center gap-3 rounded-xl border border-line bg-card px-4 py-2.5 text-[14px] text-ink transition hover:-translate-y-0.5 hover:border-primary hover:shadow-card"
            >
              <span className="text-[11px] text-faint">{n}</span>
              {label}
              <ArrowUpRight size={15} className="text-primary transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </button>
          ))}
        </div>
      </section>

      <div className="mt-8">
        <div className="space-y-6">
          <section id="entreprise" className="card scroll-mt-24 p-6 md:p-8">
            <p className="eyebrow">01 / Découvrir</p>
            <h2 className="mt-2 text-[26px] font-semibold text-ink">L’entreprise</h2>
            <p className="mt-4 text-[15px] leading-relaxed text-muted">{about}</p>
            <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
              {info.map((item) => (
                <div key={item.label} className="rounded-xl border border-line bg-surface p-4 text-center transition hover:-translate-y-0.5 hover:border-primary">
                  <item.icon size={20} className="mx-auto text-primary" />
                  <p className="mt-2 text-[12px] text-muted">{item.label}</p>
                  <p className="mt-0.5 text-[14px] font-semibold text-ink">{item.value}</p>
                </div>
              ))}
            </div>
            {c.match != null && (
              <div className="mt-6 rounded-xl border border-line bg-primary-soft p-5">
                <p className="text-[11px] font-semibold uppercase tracking-widest text-primary">Compatibilité avec votre profil</p>
                <div className="mt-3 h-2 rounded-full bg-chip">
                  <div className="h-full rounded-full bg-success transition-all duration-700" style={{ width: `${c.match}%` }} />
                </div>
                <p className="mt-3 text-[14px] text-ink">
                  <strong>{c.match}%</strong> · En phase : {c.match_skills?.join(', ') || 'aucune'}
                </p>
                <p className="text-[14px] text-ink">À développer : {c.missing_skills?.join(', ') || 'rien d’identifié'}</p>
                <p className="mt-1 text-[12px] text-muted">Estimation par mots-clés, pas une probabilité d’embauche.</p>
              </div>
            )}
          </section>

          <section id="opportunites" className="card scroll-mt-24 p-6 md:p-8">
            <p className="eyebrow">02 / Postuler</p>
            <h2 className="mt-2 text-[26px] font-semibold text-ink">Les opportunités</h2>
            <p className="mt-4 text-[15px] leading-relaxed text-muted">
              Aucune offre de stage publiée n’est connue pour cette entreprise : une candidature spontanée est recommandée.
              Préparez votre CV et votre message, puis vérifiez tout avant l’envoi.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button onClick={() => setApply(true)} className="btn-primary">Préparer ma candidature</button>
              {!t && <button onClick={() => addToTracking(c.id)} className="btn-outline">Ajouter au suivi</button>}
              <button onClick={() => navigate(`/cv-studio?company=${encodeURIComponent(c.id)}`)} className="btn-outline">
                <FileText size={17} /> CV + e-mail
              </button>
              <button onClick={() => askAssistant(c.id)} className="btn-outline">
                <Sparkles size={17} /> Demander à l’IA
              </button>
            </div>
          </section>

          <section id="contact" className="card scroll-mt-24 p-6 md:p-8">
            <p className="eyebrow">03 / Faire le premier pas</p>
            <h2 className="mt-2 text-[26px] font-semibold text-ink">Prendre contact</h2>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-line border-t-[3px] border-t-gold bg-white p-5 sm:p-6">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted">01 / Le contact</p>
                <h3 className="mt-3 text-[16px] font-bold text-primary">Comment souhaitez-vous contacter l’entreprise ?</h3>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button type="button" onClick={() => { setContactMethod('email'); setApply(true) }} aria-pressed={contactMethod === 'email'} className={`inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-[13px] font-semibold transition-all ${contactMethod === 'email' ? 'border-primary bg-primary text-white shadow-card' : 'border-line bg-white text-ink hover:border-primary hover:bg-primary-soft'}`}>
                    <Mail size={17} /> Contacter via E-mail
                  </button>
                  {whatsappUrl ? (
                    <a
                      href={whatsappUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={() => setContactMethod('whatsapp')}
                      aria-label={`Contacter ${c.short} via WhatsApp`}
                      className={`inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-[13px] font-semibold transition-all ${contactMethod === 'whatsapp' ? 'border-primary bg-primary text-white shadow-card' : 'border-line bg-white text-ink hover:border-primary hover:bg-primary-soft'}`}
                    >
                      <MessageCircle size={17} /> Contacter via WhatsApp
                    </a>
                  ) : (
                    <p role="status" className="self-center text-[13px] text-muted">Numéro WhatsApp non disponible ou invalide.</p>
                  )}
                </div>
              </div>
              <div className="rounded-2xl border border-line border-t-[3px] border-t-[#dc8796] bg-white p-5 sm:p-6">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted">02 / Votre objectif</p>
                <label className="mt-3 block text-[16px] font-bold text-primary" htmlFor="company-application-goal">Que recherchez-vous ?</label>
                <select id="company-application-goal" value={goal} onChange={(event) => setGoal(event.target.value)} className="mt-1.5 w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] font-normal outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10">
                  <option value="stage">Stage / PFE</option>
                  <option value="emploi">Emploi</option>
                  <option value="spontanee">Candidature spontanée</option>
                </select>
                <p className="mt-2 text-[12px] text-muted">Ce choix personnalise votre message et votre candidature.</p>
              </div>
            </div>
            <ul className="mt-5 space-y-4 text-[14px] text-muted">
              <li className="flex gap-3">
                <MapPin size={18} className="mt-0.5 shrink-0 text-primary" />
                <span>
                  {c.adresse || 'Adresse non communiquée'}
                  {c.distance_km != null && (
                    <strong className="mt-1 block text-ink">
                      {c.distance_km} km de chez vous{c.coord_exacte ? '' : ' (approx.)'}
                    </strong>
                  )}
                </span>
              </li>
              <li className="flex gap-3">
                <Phone size={18} className="mt-0.5 shrink-0 text-primary" />
                {c.telephone ? <a className="text-primary hover:underline" href={`tel:${c.telephone}`}>{c.telephone}</a> : 'Téléphone non communiqué'}
              </li>
              <li className="flex gap-3">
                <Globe size={18} className="mt-0.5 shrink-0 text-primary" />
                {c.site_web ? (
                  <a className="break-all text-primary hover:underline" href={c.site_web} target="_blank" rel="noopener noreferrer">
                    {c.site_web}
                  </a>
                ) : 'Pas de site web'}
              </li>
              {c.lien_maps && (
                <li className="flex gap-3">
                  <ExternalLink size={18} className="mt-0.5 shrink-0 text-primary" />
                  <a className="text-primary hover:underline" href={c.lien_maps} target="_blank" rel="noopener noreferrer">
                    Ouvrir dans Google Maps
                  </a>
                </li>
              )}
            </ul>
            <button onClick={() => setApply(true)} className="btn-primary mt-6 w-full">Préparer ma candidature</button>
          </section>

          {c.similar?.length > 0 && (
            <section className="card p-6 md:p-8">
              <h2 className="text-[22px] font-semibold text-ink">Entreprises similaires</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {c.similar.map((similar) => (
                  <button
                    key={similar.id}
                    onClick={() => navigate(`/entreprises/${encodeURIComponent(similar.id)}`)}
                    className="flex items-center gap-3 rounded-xl border border-line p-3 text-left transition hover:-translate-y-0.5 hover:border-primary hover:shadow-pop"
                  >
                    <CompanyLogo company={similar} size="sm" />
                    <span className="min-w-0">
                      <span className="block truncate text-[14px] font-medium text-ink">{similar.short}</span>
                      <span className="text-[12px] text-muted">{similar.quartier} · score {similar.score}</span>
                    </span>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      {apply && <ApplyModal company={c} contactMethod={contactMethod} goal={goal} onClose={() => setApply(false)} />}
    </div>
  )
}
