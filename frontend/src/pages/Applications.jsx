import clsx from 'clsx'
import { Bell, CalendarDays, Check, ChevronRight, Clock, Download, ExternalLink, FileText, Mail, MoreHorizontal, Plus, RefreshCw, Sparkles, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, cvUrl, exportUrl } from '../api'
import ApplyModal from '../components/company/ApplyModal'
import CompanyLogo from '../components/ui/CompanyLogo'
import Modal from '../components/ui/Modal'
import { fmtDate, STATUS_DOT } from '../data/data'
import { useStore } from '../store/useStore'

const field = 'mt-1.5 w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] font-normal outline-none focus:border-primary'
const REVIEW_STATUSES = ['En cours de traitement', 'Entretien programmé', 'Acceptée', 'Refusée']

function suggestedReviewStatus(classification) {
  return REVIEW_STATUSES.includes(classification) ? classification : 'En cours de traitement'
}

function formatEmailDate(value) {
  if (!value) return 'Date inconnue'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

function Card({ app, statuts, onMenu, menuOpen, onMove, onRemove, onEdit, onOpen, onDetails }) {
  const idx = statuts.indexOf(app.statut)
  const last = idx === statuts.length - 1
  return (
    <article draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', app.id)} className="card relative cursor-grab p-4 active:cursor-grabbing">
      <div className="flex items-start justify-between">
        <CompanyLogo company={app} size="sm" />
        <button onClick={(event) => { event.stopPropagation(); onMenu() }} aria-label="Actions" className="rounded-lg p-1 text-muted hover:bg-surface"><MoreHorizontal size={18} /></button>
      </div>
      {menuOpen && (
        <div className="absolute right-3 top-12 z-10 max-h-72 w-56 overflow-y-auto rounded-xl border border-line bg-white p-1.5 shadow-pop">
          <button onClick={onEdit} className="block w-full rounded-lg px-3 py-2 text-left text-[13px] font-semibold hover:bg-surface">Modifier les détails</button>
          {app.company_id && <button onClick={onOpen} className="block w-full rounded-lg px-3 py-2 text-left text-[13px] hover:bg-surface">Voir la fiche entreprise</button>}
          {statuts.filter((s) => s !== app.statut).map((s) => (
            <button key={s} onClick={() => onMove(s)} className="block w-full rounded-lg px-3 py-2 text-left text-[13px] hover:bg-surface">Déplacer vers « {s} »</button>
          ))}
          <button onClick={onRemove} className="block w-full rounded-lg px-3 py-2 text-left text-[13px] text-red-600 hover:bg-red-50">Supprimer</button>
        </div>
      )}
      <h3 className="mt-3 text-[15px] font-medium leading-snug">{app.short}</h3>
      <p className="mt-1 text-[12px] text-muted">{app.poste || 'Poste non précisé'} · {app.source}</p>
      <div className="mt-3 space-y-1.5 border-t border-line pt-3 text-[12px] text-muted">
        <p className="flex items-center gap-2"><Clock size={14} />{app.date_candidature ? `Envoyée le ${fmtDate(app.date_candidature)}` : 'Pas encore envoyée'}</p>
        {app.fichier_cv ? (
          <a href={cvUrl(app.id)} className="flex items-center gap-2 text-primary hover:underline"><FileText size={14} />{['Brouillon', 'À envoyer'].includes(app.statut) ? 'CV prêt' : 'CV associé'}</a>
        ) : (
          <p className="flex items-center gap-2"><FileText size={14} />Aucun CV</p>
        )}
        {app.lien_offre && <a href={app.lien_offre} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-primary hover:underline"><ExternalLink size={14} />Rouvrir la recherche Indeed</a>}
      </div>
      {app.relance_due && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-gold-soft px-3 py-2 text-[12px] font-semibold text-gold-ink"><Bell size={14} />Relance à faire ({fmtDate(app.date_relance)})</div>
      )}
      {app.date_entretien && <p className="mt-3 rounded-lg bg-success-soft px-3 py-2 text-[12px] font-semibold text-success">Entretien prévu le {fmtDate(app.date_entretien)}</p>}
      {app.remarque && <p className="mt-3 line-clamp-2 text-[12px] italic text-muted">{app.remarque}</p>}
      <button onClick={onDetails} className="mt-3 text-[12px] font-semibold text-primary hover:underline">Voir les détails et l’historique</button>
      {!last && (
        <button onClick={() => onMove(statuts[idx + 1])} className="mt-4 flex w-full items-center justify-between text-[12px] font-medium text-primary">
          Passer à « {statuts[idx + 1]} » <ChevronRight size={16} />
        </button>
      )}
    </article>
  )
}

export default function Applications() {
  const { tracking, counts, relances, meta, settings, setSetting, updateTracking, removeTracking, openCompany, refreshTracking } = useStore()
  const navigate = useNavigate()
  const statuts = meta.statuts
  const [view, setView] = useState('kanban')
  const [menuId, setMenuId] = useState(null)
  const [dragOver, setDragOver] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [applyFor, setApplyFor] = useState(false)
  const [edit, setEdit] = useState(null)
  const [details, setDetails] = useState(null)
  const [filter, setFilter] = useState('all')
  const [companyFilter, setCompanyFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [dateStart, setDateStart] = useState('')
  const [dateEnd, setDateEnd] = useState('')
  const [emailSync, setEmailSync] = useState(null)
  const [emailReviews, setEmailReviews] = useState([])
  const [emailSyncBusy, setEmailSyncBusy] = useState(false)
  const [automaticFollowupBusy, setAutomaticFollowupBusy] = useState(false)
  const [emailSyncError, setEmailSyncError] = useState('')
  const [reviewChoices, setReviewChoices] = useState({})
  const [reviewBusyId, setReviewBusyId] = useState('')

  const visible = tracking.filter((a) => (
    (filter === 'all' || a.statut === filter)
    && (sourceFilter === 'all' || a.source === sourceFilter)
    && (!companyFilter || `${a.entreprise} ${a.short}`.toLowerCase().includes(companyFilter.toLowerCase()))
    && (!dateStart || (a.date_candidature && a.date_candidature >= dateStart))
    && (!dateEnd || (a.date_candidature && a.date_candidature <= dateEnd))
  ))
  const sent = tracking.filter((a) => a.date_candidature && !['Offre expirée ou candidature annulée'].includes(a.statut)).length
  const stats = [
    { label: 'Entreprises suivies', value: tracking.length },
    { label: 'Candidatures envoyées', value: sent },
    { label: 'Entretiens / acceptées', value: (counts['Entretien programmé'] || 0) + (counts.Acceptée || 0) },
    { label: 'Relances à faire', value: relances.length },
  ]
  const move = (a, s) => updateTracking(a.id, { statut: s }, `Statut : ${s}`)
  const refreshEmailSync = async () => {
    const [status, reviews] = await Promise.all([api.emailSyncStatus(), api.emailSyncReviews()])
    setEmailSync(status)
    setEmailReviews(reviews.items)
  }

  useEffect(() => {
    let active = true
    Promise.all([api.emailSyncStatus(), api.emailSyncReviews()])
      .then(([status, reviews]) => {
        if (!active) return
        setEmailSync(status)
        setEmailReviews(reviews.items)
      })
      .catch((error) => {
        if (active) setEmailSyncError(error.message || 'Impossible de charger le statut Gmail.')
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const handleGmailConnected = (event) => {
      if (event.origin !== window.location.origin || event.data?.type !== 'bookjob-gmail-connected') return
      setEmailSyncError('')
      Promise.all([api.emailSyncStatus(), api.emailSyncReviews()])
        .then(([status, reviews]) => {
          setEmailSync(status)
          setEmailReviews(reviews.items)
        })
        .catch((error) => {
          setEmailSyncError(error.message || 'Impossible de charger le statut Gmail.')
        })
    }
    window.addEventListener('message', handleGmailConnected)
    return () => window.removeEventListener('message', handleGmailConnected)
  }, [])

  const synchronizeEmails = async () => {
    setEmailSyncBusy(true)
    setEmailSyncError('')
    try {
      await api.runEmailSync()
      await refreshEmailSync()
      await refreshTracking()
    } catch (error) {
      setEmailSyncError(error.message || 'La synchronisation Gmail a échoué.')
      try { await refreshEmailSync() } catch { /* Keep the original synchronization error visible. */ }
    } finally {
      setEmailSyncBusy(false)
    }
  }

  const setAutomaticFollowups = async (enabled) => {
    if (enabled && !window.confirm(
      'BookJob enverra depuis ton Gmail une relance au recruteur après 7 jours sans réponse, une seule fois par candidature envoyée. Continuer ?',
    )) return
    setAutomaticFollowupBusy(true)
    try {
      const saved = await setSetting({ automaticFollowups: enabled })
      if (saved) await refreshEmailSync()
    } finally {
      setAutomaticFollowupBusy(false)
    }
  }

  const resolveEmailReview = async (message) => {
    const choice = reviewChoices[message.message_id] || {}
    const trackingId = choice.tracking_id || tracking[0]?.id
    const status = choice.status || suggestedReviewStatus(message.classification)
    if (!trackingId) {
      setEmailSyncError('Ajoutez d’abord une candidature au suivi avant d’associer une réponse.')
      return
    }
    if (!REVIEW_STATUSES.includes(status)) {
      setEmailSyncError('Le statut choisi pour cette réponse est invalide.')
      return
    }
    setEmailSyncError('')
    setReviewBusyId(message.message_id)
    try {
      await api.resolveEmailSyncReview(message.message_id, { tracking_id: trackingId, status })
      await refreshEmailSync()
      await refreshTracking()
    } catch (error) {
      setEmailSyncError(error.message || 'Impossible de confirmer cette association.')
    } finally {
      setReviewBusyId('')
    }
  }

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 md:px-8" onClick={() => setMenuId(null)}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow !text-[#31517f]">Suivi</p>
          <h1 className="page-title mt-3">Mes candidatures</h1>
          <p className="mt-3 text-[16px] text-muted">Les candidatures préparées restent en brouillon jusqu’à ce que vous confirmiez leur envoi.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a className="btn-outline !px-4 !py-3.5" href={exportUrl}><Download size={17} /> Exporter CSV</a>
          <button type="button" className="btn-outline !px-4 !py-3.5" onClick={() => setShowAdd(true)}><Plus size={18} /> Offre trouvée ailleurs</button>
          <button type="button" className="btn-primary !px-5 !py-3.5" onClick={() => setApplyFor(true)}><Plus size={18} /> Nouvelle candidature</button>
        </div>
      </div>

      {relances.length > 0 && (
        <div role="status" className="mt-6 rounded-xl bg-gold-soft px-4 py-3 text-[14px] text-gold-ink">
          <strong>{relances.length} relance(s) à faire :</strong> {relances.map((r) => r.short).join(', ')}
        </div>
      )}

      <section className="card mt-5 p-5" aria-label="Suivi des e-mails de recrutement">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex gap-3">
            <Mail className="mt-0.5 text-primary" size={20} />
            <div>
              <h2 className="text-[16px] font-semibold">Réponses reçues par e-mail</h2>
              <p className="mt-1 text-[13px] text-muted">
                {emailSync?.gmail?.connected
                  ? emailSync.gmail.read_authorized
                    ? `Gmail connecté · dernière vérification : ${emailSync.last_checked ? fmtDate(emailSync.last_checked) : 'jamais'}`
                    : 'Gmail connecté, mais l’accès en lecture manque. Clique sur « Renouveler Gmail » et autorise la lecture des e-mails.'
                  : 'Connectez Gmail pour rechercher les réponses aux candidatures.'}
              </p>
              <p className="mt-1 text-[12px] text-muted">
                Google demandera l’accès Gmail en lecture pour vérifier les réponses. L’envoi et les brouillons nécessitent aussi leurs autorisations respectives.
              </p>
              {emailSync?.status === 'error' && emailSync.error && emailSync.error !== emailSyncError && <p role="alert" className="mt-1 text-[13px] text-red-700">{emailSync.error}</p>}
              {emailSyncError && <p role="alert" className="mt-1 text-[13px] text-red-700">{emailSyncError}</p>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="btn-outline" onClick={() => window.open('/api/google/connect', 'bookjob-google-oauth', 'popup,width=520,height=680')}>
              {emailSync?.gmail?.connected ? 'Renouveler Gmail' : 'Connecter Gmail'}
            </button>
            <button className="btn-primary" disabled={emailSyncBusy || !emailSync?.gmail?.connected || !emailSync.gmail.read_authorized} onClick={synchronizeEmails}>
              <RefreshCw size={16} className={emailSyncBusy ? 'animate-spin' : ''} />{emailSyncBusy ? 'Synchronisation…' : 'Synchroniser'}
            </button>
          </div>
        </div>
        <div className="mt-4 border-t border-line pt-3">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={!!settings.automaticFollowups}
              disabled={automaticFollowupBusy || (!settings.automaticFollowups && (!emailSync?.gmail?.connected || !emailSync.gmail.read_authorized || !emailSync.gmail.send_authorized))}
              onChange={(event) => setAutomaticFollowups(event.target.checked)}
              className="mt-1 h-4 w-4 accent-primary"
            />
            <span>
              <span className="block text-[13px] font-semibold">Relances automatiques par e-mail</span>
              <span className="mt-0.5 block text-[12px] text-muted">
                Après 7 jours sans réponse, une seule relance depuis Gmail pour chaque candidature marquée « Candidature envoyée ».
                BookJob vérifie d’abord les réponses; aucune relance ne part si une réponse est détectée.
              </span>
              {emailSync?.automatic_followups?.failed > 0 && (
                <span role="alert" className="mt-1 block text-[12px] text-red-700">
                  {emailSync.automatic_followups.failed} relance(s) n’ont pas pu être confirmées. Vérifie Gmail; BookJob ne les renverra pas automatiquement.
                </span>
              )}
              {emailSync?.automatic_followups?.uncertain > 0 && (
                <span role="alert" className="mt-1 block text-[12px] text-gold-ink">
                  {emailSync.automatic_followups.uncertain} envoi(s) interrompu(s) ou incertain(s). Vérifie Gmail avant toute relance manuelle.
                </span>
              )}
              {emailSync?.automatic_followups?.sent > 0 && (
                <span className="mt-1 block text-[12px] text-success">
                  {emailSync.automatic_followups.sent} relance(s) automatique(s) envoyée(s).
                </span>
              )}
              {(!emailSync?.gmail?.connected || !emailSync.gmail.read_authorized || !emailSync.gmail.send_authorized) && (
                <span className="mt-1 block text-[12px] text-gold-ink">
                  Connecte ou renouvelle Gmail avec les autorisations de lecture et d’envoi pour activer cette option.
                </span>
              )}
              {automaticFollowupBusy && <span role="status" className="mt-1 block text-[12px] text-muted">Enregistrement…</span>}
            </span>
          </label>
        </div>
        {emailReviews.length > 0 && (
          <div className="mt-5 border-t border-line pt-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-[16px] font-semibold text-ink">À vérifier et associer</h3>
                <p className="mt-1 text-[12px] text-muted">Confirmez à quelle candidature chaque réponse correspond.</p>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-gold-soft px-3 py-1.5 text-[12px] font-semibold text-gold-ink">
                <Mail size={14} />{emailReviews.length} e-mail{emailReviews.length === 1 ? '' : 's'} en attente
              </span>
            </div>
            <ul className="mt-4 grid gap-4 xl:grid-cols-2">
              {emailReviews.map((message) => {
                const choice = reviewChoices[message.message_id] || {}
                const suggestedStatus = suggestedReviewStatus(message.classification)
                const senderName = message.sender?.match(/^(.+?)\s*<[^>]+>$/)?.[1]?.replaceAll('"', '').trim()
                const senderAddress = message.sender?.match(/<([^>]+)>$/)?.[1] || message.sender
                const senderInitial = (senderName || senderAddress || '?').slice(0, 1).toUpperCase()
                return (
                  <li key={message.message_id} className="group overflow-hidden rounded-2xl border border-line bg-white shadow-card transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-pop">
                    <div className="border-b border-line bg-gradient-to-r from-primary-soft/70 via-white to-white p-4 sm:p-5">
                      <div className="flex min-w-0 items-start gap-3">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white text-primary shadow-card ring-1 ring-line">
                          {senderInitial === '?' ? <UserRound size={20} /> : <span className="text-[15px] font-bold">{senderInitial}</span>}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="min-w-0 break-all text-[13px] font-semibold text-ink">{senderName || senderAddress || 'Expéditeur inconnu'}</p>
                            <span className="inline-flex items-center gap-1 rounded-full bg-gold-soft px-2.5 py-1 text-[10px] font-semibold text-gold-ink">
                              <Sparkles size={12} />À vérifier
                            </span>
                          </div>
                          {senderName && <p className="mt-0.5 break-all text-[11px] text-muted">{senderAddress}</p>}
                          <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted">
                            <CalendarDays size={13} />{formatEmailDate(message.received_at)}
                          </p>
                        </div>
                      </div>
                      <h4 className="mt-4 break-words text-[15px] font-semibold leading-snug text-navy-900">{message.subject || '(sans objet)'}</h4>
                      {message.snippet && (
                        <p className="mt-2 line-clamp-3 rounded-xl border border-line/70 bg-white/80 px-3.5 py-3 text-[12px] leading-relaxed text-muted">
                          {message.snippet}
                        </p>
                      )}
                    </div>
                    <div className="space-y-3 p-4 sm:p-5">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <label className="block text-[11px] font-semibold uppercase tracking-wide text-muted">Candidature concernée
                          <select value={choice.tracking_id || tracking[0]?.id || ''} onChange={(event) => setReviewChoices({ ...reviewChoices, [message.message_id]: { ...choice, tracking_id: event.target.value } })} className="mt-1.5 block w-full min-w-0 rounded-xl border border-line bg-white px-3 py-2.5 text-[12px] font-medium normal-case tracking-normal text-ink outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10" disabled={!tracking.length}>
                            {tracking.map((application) => <option key={application.id} value={application.id}>{application.short} — {application.poste || 'Poste non précisé'}</option>)}
                          </select>
                        </label>
                        <label className="block text-[11px] font-semibold uppercase tracking-wide text-muted">Statut suggéré
                          <select value={choice.status || suggestedStatus} onChange={(event) => setReviewChoices({ ...reviewChoices, [message.message_id]: { ...choice, status: event.target.value } })} className="mt-1.5 block w-full rounded-xl border border-line bg-white px-3 py-2.5 text-[12px] font-medium normal-case tracking-normal text-ink outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10">
                            {REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}
                          </select>
                        </label>
                      </div>
                      <button type="button" className="btn-primary flex w-full justify-center !py-2.5" disabled={!tracking.length || reviewBusyId === message.message_id} onClick={() => resolveEmailReview(message)}>
                        <Check size={16} />{reviewBusyId === message.message_id ? 'Association…' : 'Confirmer l’association'}
                      </button>
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </section>

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="card flex items-center justify-between px-5 py-6">
            <span className="text-[14px] text-muted">{s.label}</span>
            <span className="text-[26px] font-semibold text-navy-900">{s.value}</span>
          </div>
        ))}
      </div>

      <div className="relative mt-5 flex items-center justify-between">
        <div className="inline-flex rounded-xl bg-chip p-1">
          {[['kanban', 'Kanban'], ['liste', 'Liste']].map(([v, l]) => (
            <button key={v} onClick={() => setView(v)} className={clsx('rounded-lg px-4 py-2 text-[14px]', view === v ? 'bg-white font-medium text-ink shadow-card' : 'text-muted')}>{l}</button>
          ))}
        </div>
      </div>

      <div className="card mt-3 flex flex-wrap items-end gap-3 p-4">
        <label className="text-[12px] font-semibold">Statut
          <select value={filter} onChange={(e) => setFilter(e.target.value)} className="mt-1 block rounded-lg border border-line bg-white px-3 py-2 text-[13px]">
            <option value="all">Tous ({tracking.length})</option>
            {statuts.map((status) => <option key={status} value={status}>{status} ({counts[status] || 0})</option>)}
          </select>
        </label>
        <label className="text-[12px] font-semibold">Entreprise
          <input value={companyFilter} onChange={(e) => setCompanyFilter(e.target.value)} className="mt-1 block rounded-lg border border-line px-3 py-2 text-[13px]" placeholder="Rechercher" />
        </label>
        <label className="text-[12px] font-semibold">Source
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="mt-1 block rounded-lg border border-line bg-white px-3 py-2 text-[13px]">
            <option value="all">Toutes</option>
            {[...new Set(tracking.map((item) => item.source).filter(Boolean))].sort().map((source) => <option key={source}>{source}</option>)}
          </select>
        </label>
        <label className="text-[12px] font-semibold">Du
          <input type="date" value={dateStart} onChange={(e) => setDateStart(e.target.value)} className="mt-1 block rounded-lg border border-line px-3 py-2 text-[13px]" />
        </label>
        <label className="text-[12px] font-semibold">Au
          <input type="date" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)} className="mt-1 block rounded-lg border border-line px-3 py-2 text-[13px]" />
        </label>
        <button className="btn-outline !py-2" onClick={() => {
          setFilter('all'); setCompanyFilter(''); setSourceFilter('all'); setDateStart(''); setDateEnd('')
        }}>Effacer les filtres</button>
      </div>

      {tracking.length === 0 ? (
        <div className="card mt-6 p-10 text-center">
          <p className="font-medium">Aucune candidature suivie.</p>
          <p className="mt-1 text-[14px] text-muted">Ajoutez des entreprises depuis la recherche ou créez une candidature.</p>
        </div>
      ) : view === 'kanban' ? (
        <div className="mt-5 flex gap-4 overflow-x-auto pb-6">
          {statuts.map((col) => {
            const items = visible.filter((a) => a.statut === col)
            return (
              <section
                key={col}
                onDragOver={(e) => { e.preventDefault(); setDragOver(col) }}
                onDragLeave={() => setDragOver(null)}
                onDrop={(e) => {
                  e.preventDefault(); setDragOver(null)
                  const a = tracking.find((x) => x.id === e.dataTransfer.getData('text/plain'))
                  if (a && a.statut !== col) move(a, col)
                }}
                className={clsx('min-h-[360px] w-[290px] shrink-0 rounded-2xl bg-[#eff3f8] p-3 transition-colors', dragOver === col && 'ring-2 ring-primary/40')}
                aria-label={col}
              >
                <header className="mb-3 flex items-center gap-2 px-2 pt-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_DOT[col] }} />
                  <h2 className="flex-1 text-[14px] font-semibold">{col}</h2>
                  <span className="flex h-6 min-w-6 items-center justify-center rounded-full bg-white px-1.5 text-[11px] font-semibold">{items.length}</span>
                </header>
                <div className="space-y-3">
                  {items.map((a) => (
                    <div key={a.id} onClick={(e) => e.stopPropagation()}>
                      <Card
                        app={a} statuts={statuts} menuOpen={menuId === a.id}
                        onMenu={() => setMenuId(menuId === a.id ? null : a.id)}
                        onMove={(s) => { move(a, s); setMenuId(null) }}
                        onRemove={() => { if (confirm(`Supprimer « ${a.short} » du suivi ?`)) removeTracking(a.id); setMenuId(null) }}
                        onEdit={() => { setEdit(a); setMenuId(null) }}
                        onOpen={() => { openCompany(a.company_id); navigate('/rechercher') }}
                        onDetails={() => setDetails(a)}
                      />
                    </div>
                  ))}
                </div>
              </section>
            )
          })}
        </div>
      ) : (
        <div className="card mt-5 overflow-x-auto">
          <table className="w-full min-w-[940px] text-left text-[14px]">
            <thead className="border-b border-line text-[12px] uppercase tracking-wider text-muted">
              <tr><th className="px-5 py-3">Entreprise</th><th className="px-5 py-3">Poste</th><th className="px-5 py-3">Envoi</th><th className="px-5 py-3">Relance</th><th className="px-5 py-3">Entretien</th><th className="px-5 py-3">Statut</th><th className="px-5 py-3">CV</th><th className="px-5 py-3" /></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {visible.map((a) => (
                <tr key={a.id}>
                  <td className="px-5 py-3 font-medium">{a.short}<span className="block text-[11px] font-normal text-faint">{a.id} · {a.source}</span></td>
                  <td className="px-5 py-3 text-muted">{a.poste || '—'}</td>
                  <td className="px-5 py-3 text-muted">{fmtDate(a.date_candidature)}</td>
                  <td className={clsx('px-5 py-3', a.relance_due ? 'font-semibold text-gold-ink' : 'text-muted')}>{fmtDate(a.date_relance)}</td>
                  <td className="px-5 py-3 text-muted">{fmtDate(a.date_entretien)}</td>
                  <td className="px-5 py-3">
                    <select value={a.statut} onChange={(e) => move(a, e.target.value)} className="rounded-lg border border-line bg-white px-2 py-1.5 text-[13px]" aria-label="Changer le statut">
                      {statuts.map((s) => <option key={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="px-5 py-3">{a.fichier_cv ? <a className="text-primary hover:underline" href={cvUrl(a.id)}>Télécharger</a> : '—'}</td>
                  <td className="px-5 py-3 text-right whitespace-nowrap">
                    <button onClick={() => setDetails(a)} className="mr-3 text-[13px] text-primary hover:underline">Détails</button>
                    <button onClick={() => setEdit(a)} className="mr-3 text-[13px] text-primary hover:underline">Modifier</button>
                    <button onClick={() => confirm(`Supprimer « ${a.short} » ?`) && removeTracking(a.id)} className="text-[13px] text-red-600 hover:underline">Supprimer</button>
                  </td>
                </tr>
              ))}
              {visible.length === 0 && <tr><td colSpan={8} className="px-5 py-10 text-center text-muted">Aucune candidature pour ce filtre.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <AddExternal onClose={() => setShowAdd(false)} />}
      {applyFor && <ApplyModal company={null} onClose={() => setApplyFor(false)} />}
      {edit && <EditModal app={edit} onClose={() => setEdit(null)} />}
      {details && <DetailsModal app={details} onClose={() => setDetails(null)} />}
    </div>
  )
}

function AddExternal({ onClose }) {
  const { meta, addExternal } = useStore()
  const [d, setD] = useState({ entreprise: '', poste: '', source: 'LinkedIn', lien_offre: '', email: '' })
  const submit = async (e) => {
    e.preventDefault()
    if (!d.entreprise.trim()) return
    if (await addExternal({ ...d, statut: 'Brouillon' })) onClose()
  }
  return (
    <Modal title="Offre trouvée ailleurs" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3.5">
        <label className="block text-[13px] font-semibold">Entreprise<input autoFocus required value={d.entreprise} onChange={(e) => setD({ ...d, entreprise: e.target.value })} className={field} /></label>
        <label className="block text-[13px] font-semibold">Poste<input value={d.poste} onChange={(e) => setD({ ...d, poste: e.target.value })} className={field} /></label>
        <label className="block text-[13px] font-semibold">Source
          <select value={d.source} onChange={(e) => setD({ ...d, source: e.target.value })} className={field}>{meta.sources.filter((s) => s !== 'Google Maps' && s !== 'Candidature directe').map((s) => <option key={s}>{s}</option>)}</select>
        </label>
        <label className="block text-[13px] font-semibold">Lien de l’offre<input type="url" value={d.lien_offre} onChange={(e) => setD({ ...d, lien_offre: e.target.value })} className={field} placeholder="https://" /></label>
        <label className="block text-[13px] font-semibold">E-mail de candidature<input type="email" value={d.email} onChange={(e) => setD({ ...d, email: e.target.value })} className={field} /></label>
        <div className="flex justify-end gap-3 pt-1"><button type="button" onClick={onClose} className="btn-outline">Annuler</button><button className="btn-primary">Ajouter</button></div>
      </form>
    </Modal>
  )
}

function EditModal({ app, onClose }) {
  const { meta, updateTracking } = useStore()
  const [d, setD] = useState({ statut: app.statut, poste: app.poste, email: app.email, lien_offre: app.lien_offre, date_candidature: app.date_candidature, date_relance: app.date_relance, date_entretien: app.date_entretien || '', remarque: app.remarque })
  const submit = async (e) => {
    e.preventDefault()
    if (await updateTracking(app.id, d, 'Candidature mise à jour')) onClose()
  }
  const set = (k) => (e) => setD({ ...d, [k]: e.target.value })
  return (
    <Modal title={app.short} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-[13px] font-semibold">Statut<select value={d.statut} onChange={set('statut')} className={field}>{meta.statuts.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label className="block text-[13px] font-semibold">Poste visé<input value={d.poste} onChange={set('poste')} className={field} /></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-[13px] font-semibold">Date d’envoi<input type="date" value={d.date_candidature} onChange={set('date_candidature')} className={field} /></label>
          <label className="block text-[13px] font-semibold">Date de relance<input type="date" value={d.date_relance} onChange={set('date_relance')} className={field} /></label>
        </div>
        <label className="block text-[13px] font-semibold">Date d’entretien (optionnelle)<input type="date" value={d.date_entretien} onChange={set('date_entretien')} className={field} /></label>
        <label className="block text-[13px] font-semibold">E-mail de contact<input type="email" value={d.email} onChange={set('email')} className={field} /></label>
        <label className="block text-[13px] font-semibold">Lien de l’offre<input value={d.lien_offre} onChange={set('lien_offre')} className={field} /></label>
        <label className="block text-[13px] font-semibold">Notes<textarea rows={3} value={d.remarque} onChange={set('remarque')} className={field} /></label>
        <div className="flex justify-end gap-3 pt-1"><button type="button" onClick={onClose} className="btn-outline">Annuler</button><button className="btn-primary">Enregistrer</button></div>
      </form>
    </Modal>
  )
}

function DetailsModal({ app, onClose }) {
  const [events, setEvents] = useState([])
  const [emails, setEmails] = useState([])
  const [sentEmails, setSentEmails] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([api.trackingEvents(app.id), api.trackingEmails(app.id), api.trackingSentEmails(app.id)])
      .then(([history, messages, sentMessages]) => {
        if (!active) return
        setEvents(history.items)
        setEmails(messages.items)
        setSentEmails(sentMessages.items)
      })
      .catch((err) => {
        if (active) setError(err.message || 'Impossible de charger les détails.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [app.id])

  return (
    <Modal title={`Détails — ${app.short}`} onClose={onClose}>
      <div className="space-y-5">
        <dl className="grid grid-cols-1 gap-x-5 gap-y-3 text-[13px] sm:grid-cols-2">
          <div><dt className="text-muted">Poste</dt><dd className="font-medium">{app.poste || 'Non précisé'}</dd></div>
          <div><dt className="text-muted">Statut</dt><dd className="font-medium">{app.statut}</dd></div>
          <div><dt className="text-muted">Source</dt><dd className="font-medium">{app.source || 'Non précisée'}</dd></div>
          <div><dt className="text-muted">Date de candidature</dt><dd className="font-medium">{app.date_candidature ? fmtDate(app.date_candidature) : 'Pas encore envoyée'}</dd></div>
          <div><dt className="text-muted">Dernière activité enregistrée</dt><dd className="font-medium">{app.derniere_activite || app.date_modification ? fmtDate(app.derniere_activite || app.date_modification) : 'Non disponible'}</dd></div>
          <div><dt className="text-muted">E-mail de contact</dt><dd className="font-medium">{app.email || 'Non renseigné'}</dd></div>
        </dl>
        {app.lien_offre && <a href={app.lien_offre} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-[13px] font-semibold text-primary hover:underline"><ExternalLink size={14} />Ouvrir l’offre</a>}

        {loading && <p className="text-[13px] text-muted">Chargement de l’historique…</p>}
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>}

        {!loading && !error && (
          <>
            <section>
              <h3 className="mb-2 text-[14px] font-semibold">Historique des statuts</h3>
              {events.length === 0 ? <p className="text-[13px] text-muted">Aucun changement de statut enregistré.</p> : (
                <ol className="space-y-2">
                  {events.map((event, index) => (
                    <li key={`${event.occurred_at}-${index}`} className="rounded-lg bg-surface px-3 py-2 text-[13px]">
                      <p className="font-medium">{event.old_status || 'Créée'} → {event.new_status}</p>
                      <p className="mt-0.5 text-[11px] text-muted">{event.source} · {event.occurred_at}</p>
                      {event.details && <p className="mt-1 text-muted">{event.details}</p>}
                    </li>
                  ))}
                </ol>
              )}
            </section>
            <section>
              <h3 className="mb-2 text-[14px] font-semibold">E-mails envoyés depuis BookJob</h3>
              {sentEmails.length === 0 ? <p className="text-[13px] text-muted">Aucun envoi Gmail enregistré pour cette candidature.</p> : (
                <ul className="space-y-3">
                  {sentEmails.map((email) => (
                    <li key={email.message_id} className="rounded-lg border border-success/30 bg-success-soft p-3 text-[13px]">
                      <p className="font-semibold">{email.subject || '(sans objet)'}</p>
                      <p className="mt-1 text-[12px] text-muted">De : {email.sender} · À : {email.recipient}</p>
                      <p className="text-[12px] text-muted">Enregistré le {new Date(email.sent_at).toLocaleString()}</p>
                      {email.attachments.length > 0 && <p className="mt-1 text-[12px]">Pièces jointes : {email.attachments.join(', ')}</p>}
                      <details className="mt-2">
                        <summary className="cursor-pointer font-semibold">Voir le contenu envoyé</summary>
                        <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-white/70 p-2 font-sans">{email.body}</pre>
                      </details>
                      <a href={email.gmail_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 font-semibold text-primary hover:underline">
                        <ExternalLink size={14} />Ouvrir le message dans Gmail · Envoyés
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section>
              <h3 className="mb-2 text-[14px] font-semibold">E-mails reçus et associés</h3>
              {emails.length === 0 ? <p className="text-[13px] text-muted">Aucun e-mail de recrutement associé.</p> : (
                <ul className="space-y-2">
                  {emails.map((email) => (
                    <li key={email.message_id} className="rounded-lg border border-line px-3 py-2 text-[13px]">
                      <p className="font-medium">{email.subject || '(sans objet)'}</p>
                      <p className="text-[11px] text-muted">{email.sender} · {email.received_at} · {email.classification}</p>
                      {email.snippet && <p className="mt-1 whitespace-pre-wrap text-muted">{email.snippet}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
        <div className="flex justify-end"><button onClick={onClose} className="btn-outline">Fermer</button></div>
      </div>
    </Modal>
  )
}
