import { useEffect, useRef, useState } from 'react'
import { api, cvUrl } from '../../api'
import Modal from '../ui/Modal'
import { useStore } from '../../store/useStore'

export default function ApplyModal({ company, onClose, onDone }) {
  const { cvs, sendApplication, applicationSendStatus, refreshTracking, refreshCvs, notify, tracking, profile, meta } = useStore()
  const existing = company?.id ? tracking.find((t) => t.id === company.id) : null
  const [ent, setEnt] = useState(company?.short || '')
  const [poste, setPoste] = useState(existing?.poste || 'Stage PFE / Data-IT')
  const offerUrl = existing?.lien_offre || ''
  const [offerDescription, setOfferDescription] = useState('')
  const [recipient, setRecipient] = useState(existing?.email || company?.email || '')
  const [contactEmails, setContactEmails] = useState([])
  const [emailLookupStatus, setEmailLookupStatus] = useState('')
  const [selectedEmailSource, setSelectedEmailSource] = useState('')
  const [gmailStatus, setGmailStatus] = useState(meta?.email || {})
  const [cvId, setCvId] = useState((cvs.find((c) => c.main) || cvs[0])?.id || '')
  const [file, setFile] = useState(null)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [coverLetter, setCoverLetter] = useState('')
  const [letterError, setLetterError] = useState('')
  const [generatingLetter, setGeneratingLetter] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [result, setResult] = useState(null)
  const [sent, setSent] = useState(false)
  const [confirmationRequested, setConfirmationRequested] = useState(false)
  const [confirmationExpiresAt, setConfirmationExpiresAt] = useState(null)
  const [coverLetterFile, setCoverLetterFile] = useState(null)
  const ref = useRef(null)
  const letterRef = useRef(null)
  const recipientTouched = useRef(false)

  useEffect(() => {
    setGmailStatus(meta?.email || {})
  }, [meta?.email])

  // Garde toujours un CV valide sélectionné (liste chargée plus tard, CV supprimé, aucun CV « principal »).
  useEffect(() => {
    setCvId((current) => (cvs.some((c) => c.id === current) ? current : (cvs.find((c) => c.main) || cvs[0])?.id || ''))
  }, [cvs])

  useEffect(() => {
    const onMessage = (event) => {
      const allowedOrigins = [window.location.origin, meta?.email?.callback_origin].filter(Boolean)
      if (!allowedOrigins.includes(event.origin) || event.data?.type !== 'bookjob-gmail-connected') return
      api.googleStatus().then((status) => {
        setGmailStatus(status)
        setErr(status.connected ? '' : 'Le compte Gmail n’a pas été connecté.')
      }).catch((error) => setErr(error.message))
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [meta?.email?.callback_origin])

  useEffect(() => {
    if (!company?.id || existing?.email || company?.email || !company?.site_web) return
    let active = true
    setEmailLookupStatus('Recherche d’adresses publiques sur le site officiel…')
    api.discoverCompanyEmails(company.id).then(({ emails }) => {
      if (!active) return
      setContactEmails(emails)
      if (emails.length) {
        setEmailLookupStatus('')
        if (!recipientTouched.current) {
          setRecipient(emails[0].email)
          setSelectedEmailSource(emails[0].source)
        }
      } else {
        setEmailLookupStatus('Aucune adresse e-mail publique trouvée sur le site officiel. Saisis ou vérifie l’adresse avant l’envoi.')
      }
    }).catch((error) => {
      if (active) setEmailLookupStatus(`Recherche impossible : ${error.message}`)
    })
    return () => { active = false }
  }, [company?.id, company?.email, company?.site_web, existing?.email])



  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    if (!ent.trim()) return setErr('Indiquez le nom de l’entreprise.')
    if (!file && !cvId) return setErr('Importez votre CV ou choisissez-en un dans votre bibliothèque.')
    if (file && !/\.pdf$/i.test(file.name)) return setErr('Format non pris en charge : PDF uniquement.')
    if (file && file.size > 5 * 1024 * 1024) return setErr('Fichier trop volumineux (5 Mo maximum).')
    const f = new FormData()
    f.append('entreprise', ent)
    f.append('poste', poste)
    f.append('statut', 'À envoyer')
    if (offerUrl.trim()) f.append('lien_offre', offerUrl.trim())
    if (recipient.trim()) f.append('email', recipient.trim())
    if (company?.id) f.append('company_id', company.id)
    if (file) f.append('file', file)
    else f.append('cv_id', cvId)
    setBusy(true)
    let r = null
    try {
      r = await api.apply(f)
    } catch (error) {
      setErr(error.message)
    }
    setBusy(false)
    if (r) {
      notify('Candidature préparée. Confirmez l’envoi auprès de l’employeur.')
      refreshTracking().catch(() => {})
      if (file) refreshCvs().catch(() => {}) // le CV importé est aussi ajouté à la bibliothèque
      setRecipient(r.email || recipient)
      setSubject(`Candidature – ${poste || 'Stage'} – ${ent}`)
      setBody(`Bonjour,\n\nJe vous adresse ma candidature pour un stage (${poste || 'Stage'}) au sein de ${ent}. Vous trouverez mon CV et ma lettre de motivation en pièces jointes.\n\nJe reste à votre disposition pour tout complément d'information ou un entretien.\n\nCordialement,\n${profile.nom || ''}${profile.email ? `\n${profile.email}` : ''}${profile.tel ? `\n${profile.tel}` : ''}`)
      setResult(r)
      onDone?.(r)
      setGeneratingLetter(true)
      setLetterError('')
      try {
        const generated = await api.genLetter({
          company_id: company?.id || undefined,
          entreprise: ent,
          secteur: company?.secteur || '',
          poste: poste || 'Stage',
          use_ai: false,
        })
        setCoverLetter(generated.lettre)
      } catch (error) {
        setLetterError(`La lettre n'a pas pu être générée automatiquement : ${error.message}. Tu peux la saisir ci-dessous.`)
      } finally {
        setGeneratingLetter(false)
      }
    }
  }

  const requestEmailConfirmation = () => {
    setErr('')
    if (!recipient.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(recipient.trim())) {
      setErr('Saisis une adresse e-mail valide pour le destinataire.')
      return
    }
    if (!subject.trim() || !body.trim()) {
      setErr('Vérifie l’objet et le message avant d’ouvrir Gmail.')
      return
    }
    const gmailUrl = new URL('https://mail.google.com/mail/')
    gmailUrl.searchParams.set('view', 'cm')
    gmailUrl.searchParams.set('fs', '1')
    gmailUrl.searchParams.set('to', recipient.trim())
    gmailUrl.searchParams.set('su', subject.trim())
    gmailUrl.searchParams.set('body', body.trim() + (coverLetter.trim() ? `\n\n--- Lettre de motivation ---\n${coverLetter.trim()}` : ''))
    const gmailWindow = window.open(gmailUrl.toString(), '_blank')
    if (!gmailWindow) {
      setErr('Le navigateur a bloqué la fenêtre Gmail. Autorise les pop-ups puis réessaie.')
      return
    }
    setConfirmationRequested(true)
    setConfirmationExpiresAt(null)
  }

  const input = 'mt-1.5 w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] font-normal outline-none focus:border-primary'
  return (
    <Modal title={result ? (sent ? 'Candidature envoyée' : 'Vérifier et envoyer') : 'Préparer ma candidature'} onClose={onClose} wide>
      {result ? (
        <div className="space-y-4">
          {sent ? (
            <div role="status" className="rounded-xl border border-success/30 bg-success-soft p-4 text-success">
              Candidature envoyée à {recipient}. Le CV et la lettre ont été joints. La relance est planifiée dans 7 jours.
            </div>
          ) : confirmationRequested ? (
            <div className="space-y-3 rounded-xl border border-success/30 bg-success-soft p-4">
              <p className="font-semibold text-success">Gmail a été ouvert avec le destinataire, l’objet et le message préremplis.</p>
              <p className="text-[13px]">La candidature n’a pas encore été envoyée. Dans Gmail, joins ton CV et, si nécessaire, ta lettre de motivation, puis clique toi-même sur « Envoyer ». BookJob ne peut pas joindre automatiquement les fichiers via le lien du navigateur.</p>
              <button type="button" className="btn-outline" onClick={() => window.open(`https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(recipient.trim())}&su=${encodeURIComponent(subject.trim())}&body=${encodeURIComponent(body.trim())}`, '_blank', 'noopener,noreferrer')}>Rouvrir Gmail</button>
              {err && <p role="alert" className="text-[13px] text-red-600">{err}</p>}
            </div>
          ) : (
            <>
              <div className="rounded-xl border border-gold/30 bg-gold-soft p-4">
                <p className="font-semibold text-gold-ink">Aucun e-mail n’a encore été envoyé.</p>
                <p className="mt-1 text-[13px] text-gold-ink">Vérifie le destinataire, le message, le CV et la lettre joints avant de cliquer sur « Envoyer ».</p>
              </div>
              {result.fichier_cv && <a href={cvUrl(result.id)} target="_blank" rel="noreferrer" className="block text-[13px] font-semibold text-primary underline">Vérifier ou télécharger le CV joint</a>}
              <label className="block text-[13px] font-semibold">Adresse e-mail du destinataire
                <input type="email" required value={recipient} onChange={(e) => setRecipient(e.target.value)} className={input} />
              </label>
              {selectedEmailSource && <p className="text-[12px] text-muted">Adresse trouvée sur le site officiel : <a href={selectedEmailSource} target="_blank" rel="noreferrer" className="underline">vérifier la source</a></p>}
              <label className="block text-[13px] font-semibold">Objet
                <input required value={subject} onChange={(e) => setSubject(e.target.value)} className={input} />
              </label>
              <label className="block text-[13px] font-semibold">Message
                <textarea required rows={8} value={body} onChange={(e) => setBody(e.target.value)} className={input} />
              </label>
              <label className="block text-[13px] font-semibold">Lettre de motivation (jointe comme fichier texte)
                <textarea rows={10} value={coverLetter} onChange={(e) => setCoverLetter(e.target.value)} className={input} placeholder={generatingLetter ? 'Génération de la lettre…' : 'Écris ou colle ta lettre de motivation ici.'} />
              </label>
              <div className="text-[13px] font-semibold">
                Fichier de lettre finalisé (facultatif, à joindre manuellement dans Gmail)
                <input ref={letterRef} type="file" accept=".pdf" className="sr-only" onChange={(e) => setCoverLetterFile(e.target.files?.[0] || null)} />
                <div className="mt-2 flex items-center gap-3">
                  <button type="button" className="btn-outline !py-2" onClick={() => letterRef.current?.click()}>
                    {coverLetterFile ? 'Changer le fichier' : 'Importer la lettre'}
                  </button>
                  <span className="truncate text-[12px] font-normal text-muted">{coverLetterFile ? coverLetterFile.name : 'PDF uniquement, 5 Mo max'}</span>
                  {coverLetterFile && <button type="button" className="text-[12px] underline" onClick={() => setCoverLetterFile(null)}>Retirer</button>}
                </div>
              </div>
              <label className="block text-[13px] font-semibold">Description de l’offre (pour un matching explicable)
                <textarea rows={6} value={offerDescription} onChange={(e) => setOfferDescription(e.target.value)} className={input} placeholder="Colle ici le texte de l’offre : missions, compétences et critères recherchés." />
                <span className="mt-1 block text-[11px] font-normal text-muted">Sans texte d’offre, BookJob indiquera qu’il s’agit d’une candidature spontanée et ne fabriquera pas de score.</span>
              </label>
              {generatingLetter && <p role="status" className="text-[13px] text-muted">Génération de la lettre de motivation…</p>}
              {letterError && <p role="alert" className="text-[13px] text-gold-ink">{letterError}</p>}
              {err && <p role="alert" className="text-[13px] text-red-600">{err}</p>}
            </>
          )}
          <div className="flex flex-wrap justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn-outline">{sent || confirmationRequested ? 'Fermer' : 'Annuler'}</button>
            {!sent && !confirmationRequested && <button type="button" disabled={busy || generatingLetter || !recipient || !subject.trim() || !body.trim()} onClick={requestEmailConfirmation} className="btn-primary">{busy ? 'Ouverture…' : 'Ouvrir Gmail et envoyer'}</button>}
          </div>
        </div>
      ) : (
      <form onSubmit={submit} className="space-y-3.5">
        <p className="rounded-lg bg-gold-soft px-3 py-2 text-[12px] text-gold-ink">Prépare ton CV et le brouillon. L’envoi ne se fera qu’après vérification et confirmation explicite.</p>
        <label className="block text-[13px] font-semibold">
          Entreprise
          <input value={ent} onChange={(e) => setEnt(e.target.value)} className={input} readOnly={!!company?.id} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-[13px] font-semibold">
            Poste visé
            <input value={poste} onChange={(e) => setPoste(e.target.value)} className={input} />
          </label>
          <div className="self-end rounded-xl bg-surface px-3.5 py-2.5 text-[13px]"><span className="font-semibold">Étape 1 sur 2</span><span className="ml-2 text-muted">Préparer le dossier</span></div>
        </div>
        <div className="text-[13px] font-semibold">
          CV utilisé
          {cvs.length > 0 && !file && (
            <select value={cvId} onChange={(e) => setCvId(e.target.value)} className={input}>
              {cvs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.main ? ' (principal)' : ''}
                </option>
              ))}
            </select>
          )}
          <input ref={ref} type="file" accept=".pdf,.doc,.docx" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <div className="mt-2 flex items-center gap-3">
            <button type="button" className="btn-outline !py-2" onClick={() => ref.current?.click()}>
              {file ? 'Changer le fichier' : 'Importer un nouveau CV'}
            </button>
            <span className="truncate text-[12px] font-normal text-muted">{file ? file.name : 'PDF ou Word, 5 Mo max'}</span>
          </div>
          {file && <p className="mt-1.5 text-[11px] font-normal text-muted">Ce CV sera aussi enregistré dans ta bibliothèque (Profil et CV Studio) pour les prochaines candidatures.</p>}
        </div>
        <label className="block text-[13px] font-semibold">E-mail de l’entreprise (facultatif)
          <input type="email" value={recipient} onChange={(e) => {
            recipientTouched.current = true
            setRecipient(e.target.value)
            setSelectedEmailSource('')
          }} className={input} placeholder="recrutement@entreprise.ma" />
        </label>
        {emailLookupStatus && <p role="status" className="text-[12px] text-muted">{emailLookupStatus}</p>}
        {contactEmails.length > 0 && (
          <div className="space-y-1 rounded-xl bg-surface p-3 text-[12px]">
            <p className="font-semibold">Adresses trouvées sur le site officiel — vérifie le destinataire avant l’envoi :</p>
            {contactEmails.map((item) => (
              <div key={`${item.email}-${item.source}`} className="flex flex-wrap items-center gap-2">
                <button type="button" onClick={() => {
                  recipientTouched.current = true
                  setRecipient(item.email)
                  setSelectedEmailSource(item.source)
                }} className="font-semibold text-primary underline">{item.email}</button>
                <a href={item.source} target="_blank" rel="noreferrer" className="text-muted underline">Source</a>
              </div>
            ))}
          </div>
        )}
        {selectedEmailSource && <p className="text-[11px] text-muted">Source sélectionnée : <a href={selectedEmailSource} target="_blank" rel="noreferrer" className="underline">page officielle</a></p>}
        {err && <p role="alert" className="text-[13px] text-red-600">{err}</p>}
        <div className="flex justify-end gap-3 pt-1">
          <button type="button" onClick={onClose} className="btn-outline">Annuler</button>
          <button type="submit" disabled={busy} className="btn-primary">{busy ? 'Préparation…' : 'Préparer le brouillon'}</button>
        </div>
      </form>
      )}
    </Modal>
  )
}
