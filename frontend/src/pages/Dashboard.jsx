import { ArrowRight, MapPin, Star } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import CompanyLogo from '../components/ui/CompanyLogo'
import BarList from '../components/ui/BarList'
import { TONES, fmtDate } from '../data/data'
import { useStore } from '../store/useStore'

export default function Dashboard() {
  const { openCompany, tracking, favorites, profile } = useStore()
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setErr(e.message))
  }, [tracking, favorites, profile])

  if (err) return <p className="p-8 text-red-600">{err}</p>
  if (!d) return <p className="p-8 text-muted">Chargement…</p>
  const k = d.kpis
  const kpis = [
    { label: 'Entreprises suivies', value: k.suivies },
    { label: 'Candidatures envoyées', value: k.envoyees },
    { label: 'Entretiens à venir', value: d.entretiens_a_venir.length },
    { label: 'Favoris', value: k.favoris },
  ]
  const missing = d.profil.items.filter((i) => !i.done)
  const profileDone = d.profil.percent >= 100
  const statuts = Object.fromEntries(Object.entries(d.par_statut).filter(([, v]) => v > 0))

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-8 md:px-8">
      <p className="eyebrow">Tableau de bord</p>
      <h1 className="page-title mt-3">Bonjour {d.nom ? d.nom.split(' ')[0] : ''}</h1>
      <p className="mt-3 text-[16px] text-muted">Voici où en sont vos recherches de stage aujourd’hui.</p>
      <a href="/dash/" className="btn-outline mt-5">Ouvrir le tableau analytique interactif</a>

      {k.relances > 0 && (
        <Link to="/candidatures" className="mt-6 block rounded-xl bg-gold-soft px-4 py-3 text-[14px] text-gold-ink">
          <strong>{k.relances} relance(s) à faire :</strong> {d.relances_dues.map((r) => r.short).join(', ')}
        </Link>
      )}

      {d.entretiens_a_venir.length > 0 && (
        <section className="mt-5 rounded-xl border border-success/20 bg-success-soft p-4">
          <h2 className="font-semibold text-success">Entretiens à venir</h2>
          <ul className="mt-2 space-y-2">
            {d.entretiens_a_venir.map((interview) => (
              <li key={interview.id} className="flex flex-wrap justify-between gap-2 text-[13px] text-ink">
                <span>{interview.short} · {interview.poste || 'Poste non précisé'}</span>
                <strong>{fmtDate(interview.date_entretien)}</strong>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="mt-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map((x) => (
          <div key={x.label} className="card flex items-center justify-between px-5 py-5">
            <span className="text-[14px] text-muted">{x.label}</span>
            <span className="text-[26px] font-semibold">{x.value}</span>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        {!profileDone && <section className="card p-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-[22px] font-normal">Votre profil</h2>
              <p className="mt-1 text-[13px] text-muted">Un profil complet améliore le CV généré et le matching.</p>
            </div>
            <span className="text-[28px] font-light text-primary">{d.profil.percent}%</span>
          </div>
          <div className="mt-4 h-2 rounded-full bg-chip"><div className="h-full rounded-full bg-gold" style={{ width: `${d.profil.percent}%` }} /></div>
          <ul className="mt-4 divide-y divide-line border-t border-line">
            {missing.slice(0, 4).map((s) => (
              <li key={s.field} className="flex items-center gap-4 py-3.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-chip text-muted">·</span>
                <p className="flex-1 text-[14px] font-semibold">Renseigner : {s.label}</p>
                <Link to="/profil" className="text-[15px] font-semibold text-primary">Compléter</Link>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[12px] text-muted">{d.nb_cv} CV dans votre bibliothèque · <Link className="text-primary" to="/cv-studio">CV Studio</Link></p>
        </section>}

        <section className={`card p-6 ${profileDone ? 'lg:col-span-2' : ''}`}>
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-[22px] font-normal">Activité récente</h2>
              <p className="mt-1 text-[13px] text-muted">Vos dernières candidatures.</p>
            </div>
            <Link to="/candidatures" className="text-[15px] font-semibold text-primary">Tout voir</Link>
          </div>
          <ul className="mt-4 divide-y divide-line border-t border-line">
            {d.recentes.length === 0 && <li className="py-6 text-[14px] text-muted">Aucune candidature envoyée pour l’instant.</li>}
            {d.recentes.map((a) => (
              <li key={a.id} className="flex items-center gap-3 py-3.5">
                <CompanyLogo company={a} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-semibold">{a.short}</p>
                  <p className="text-[12px] text-muted">{a.poste || '—'} · {fmtDate(a.date_candidature)}</p>
                </div>
                <span className={`rounded-md px-3 py-1 text-[13px] font-medium ${a.statut === 'Entretien' || a.statut === 'Accepté' ? 'bg-success-soft text-success' : 'bg-chip text-muted'}`}>{a.statut}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <section className="card p-6"><h2 className="mb-4 text-[18px] font-medium">Suivi par statut</h2><BarList data={statuts} /></section>
        <section className="card p-6"><h2 className="mb-4 text-[18px] font-medium">Entreprises par secteur</h2><BarList data={d.par_secteur} color="var(--gold)" /></section>
        <section className="card p-6"><h2 className="mb-4 text-[18px] font-medium">Score moyen par secteur</h2><BarList data={d.score_moyen_secteur} color="var(--success)" /></section>
      </div>

      <section className="card mt-5 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-[22px] font-normal">Recommandées pour vous</h2>
            <p className="mt-1 text-[13px] text-muted">{profile.competences ? 'Selon vos compétences et le score Google Maps.' : 'Les mieux notées (ajoutez vos compétences pour personnaliser).'}</p>
          </div>
          <Link to="/rechercher" className="flex items-center gap-2 text-[15px] font-semibold text-primary">Voir toutes <ArrowRight size={17} /></Link>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {d.recommandees.map((c) => (
            <Link key={c.id} to="/rechercher" onClick={() => openCompany(c.id)} className="group overflow-hidden rounded-2xl border border-line transition-shadow hover:shadow-pop">
              <div className="relative h-[116px]" style={{ background: `linear-gradient(135deg, ${(TONES[c.tone] || TONES.blue).bg}, #ffffff 140%)` }}>
                <span className="absolute -right-6 -top-8 h-28 w-28 rounded-full opacity-60" style={{ background: (TONES[c.tone] || TONES.blue).fg, filter: 'blur(40px)' }} aria-hidden="true" />
                <span className="absolute right-3 top-3 rounded-md bg-white/90 px-2.5 py-1 text-[13px] font-medium text-success shadow-card">{c.match != null ? `${c.match}% profil` : `Score ${c.score}`}</span>
                <CompanyLogo company={c} size="xl" className="absolute -bottom-8 left-5 shadow-pop ring-4 ring-white" />
              </div>
              <div className="px-5 pb-5 pt-11">
                <h3 className="text-[19px] font-normal leading-snug group-hover:text-primary">{c.short}</h3>
                <p className="mt-1 text-[13px] text-muted">{c.secteur}</p>
                <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
                  <span className="inline-flex items-center gap-1"><MapPin size={13} />{c.quartier}</span>
                  {c.note != null && <span className="inline-flex items-center gap-1"><Star size={13} className="text-gold" fill="currentColor" />{c.note}{c.nb_avis ? ` (${c.nb_avis} avis)` : ''}</span>}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">{(c.match_skills || []).slice(0, 3).map((s) => <span key={s} className="tag">{s}</span>)}</div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
