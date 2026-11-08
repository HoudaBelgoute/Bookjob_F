import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import Modal from '../ui/Modal'
import { useStore } from '../../store/useStore'

export default function ApplyModal({
  company,
  contactMethod: initialContactMethod = 'email',
  goal: initialGoal = 'stage',
  onClose,
  onDone,
}) {
  const { cvs, refreshTracking, refreshCvs, notify, tracking, profile, meta, updateTracking } = useStore()
  const existing = company?.id ? tracking.find((t) => t.id === company.id) : null
  const [ent, setEnt] = useState(company?.short || '')
  const initialPoste = initialGoal === 'emploi' ? 'Emploi' : initialGoal === 'spontanee' ? 'Candidature spontanée' : 'Stage PFE / Data-IT'
  const [poste, setPoste] = useState(existing?.poste || initialPoste)
  const contactMethod = initialContactMethod
  const [phone, setPhone] = useState(company?.telephone || '')
  const [candidateName, setCandidateName] = useState(profile.nom || '')
  const [candidateEmail, setCandidateEmail] = useState(profile.email || '')
  const [candidatePhone, setCandidatePhone] = useState(profile.tel || '')
  const [candidateCity, setCandidateCity] = useState(profile.ville || '')
  const offerUrl = existing?.lien_offre || ''
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
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [result, setResult] = useState(null)
  const [sent, setSent] = useState(false)
  const [confirmationRequested, setConfirmationRequested] = useState(false)
  const [secureSendPending, setSecureSendPending] = useState(false)
  const [consent, setConsent] = useState(false)
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

  useEffect(() => {
    if (!secureSendPending || !result?.id || sent) return undefined
    let active = true
    const checkStatus = async () => {
      try {
        const status = await api.applicationSendStatus(result.id)
        if (!active) return
        if (status.sent) {
          setSent(true)
          setSecureSendPending(false)
          setErr('')
          notify('Votre candidature a été envoyée.')
          refreshTracking().catch((error) => setErr(error.message))
        } else {
          setConfirmationExpiresAt(status.expires_at)
        }
      } catch (error) {
        if (active) setErr(error.message)
      }
    }
    checkStatus()
    const timer = window.setInterval(checkStatus, 3000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [secureSendPending, result?.id, sent, notify, refreshTracking])

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    const errors = {}
    if (!ent.trim()) errors.ent = 'Indiquez le nom de l’entreprise.'
    if (!poste.trim()) errors.poste = 'Indiquez le poste visé.'
    if (!candidateName.trim()) errors.candidateName = 'Indiquez votre nom et prénom.'
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(candidateEmail.trim())) errors.candidateEmail = 'Indiquez une adresse e-mail valide.'
    if (candidatePhone.replace(/\D/g, '').length < 8) errors.candidatePhone = 'Indiquez un numéro de téléphone valide.'
    if (!file && !cvId) errors.cv = 'Importez un CV ou choisissez-en un dans votre bibliothèque.'
    if (file && !/\.pdf$/i.test(file.name)) errors.cv = 'Format accepté : PDF uniquement.'
    if (file && file.size > 5 * 1024 * 1024) errors.cv = 'Le CV ne doit pas dépasser 5 Mo.'
    if (coverLetterFile && !/\.pdf$/i.test(coverLetterFile.name)) errors.coverLetter = 'Format accepté : PDF uniquement.'
    if (coverLetterFile && coverLetterFile.size > 5 * 1024 * 1024) errors.coverLetter = 'La lettre ne doit pas dépasser 5 Mo.'
    if (!consent) errors.consent = 'Votre accord est nécessaire pour transmettre les informations au recruteur.'
    if (contactMethod === 'email' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(recipient.trim())) {
      errors.recipient = 'Indiquez une adresse e-mail valide pour le recruteur.'
    }
    if (contactMethod === 'whatsapp' && phone.replace(/\D/g, '').length < 8) {
      errors.phone = 'Indiquez un numéro WhatsApp valide pour l’entreprise.'
    }
    setFieldErrors(errors)
    if (Object.keys(errors).length) return

    const message = body.trim() || `Bonjour,\n\nJe vous adresse ma candidature pour ${poste} au sein de ${ent}. Vous trouverez mon CV${coverLetter.trim() || coverLetterFile ? ' et ma lettre de motivation' : ''} en pièce jointe.\n\nJe reste à votre disposition pour tout complément d’information ou entretien.`
    const candidateDetails = [candidateName.trim(), candidateCity.trim(), candidateEmail.trim(), candidatePhone.trim()]
      .filter(Boolean)
      .join('\n')
    const generatedBody = `${message}\n\nCordialement,\n${candidateDetails}`
    const externalMessage = coverLetter.trim()
      ? `${generatedBody}\n\n--- Lettre de motivation ---\n${coverLetter.trim()}`
      : generatedBody
    const subjectLine = `Candidature – ${poste} – ${ent}`
    const externalWindow = contactMethod === 'whatsapp' || !(gmailStatus?.connected && gmailStatus?.draft_authorized)
      ? window.open('', '_blank')
      : null
    if ((contactMethod === 'whatsapp' || !(gmailStatus?.connected && gmailStatus?.draft_authorized)) && !externalWindow) {
      setErr('Le navigateur a bloqué la fenêtre de contact. Autorisez les pop-ups puis réessayez.')
      return
    }

    const f = new FormData()
    f.append('entreprise', ent)
    f.append('poste', poste)
    f.append('statut', 'À envoyer')
    if (offerUrl.trim()) f.append('lien_offre', offerUrl.trim())
    if (contactMethod === 'email' && recipient.trim()) f.append('email', recipient.trim())
    if (company?.id) f.append('company_id', company.id)
    if (file) f.append('file', file)
    else f.append('cv_id', cvId)
    setBusy(true)
    let application = null
    try {
      application = await api.apply(f)
      setResult(application)
      onDone?.(application)
      refreshTracking().catch((error) => setErr(error.message))
      if (file) refreshCvs().catch((error) => setErr(error.message))
      setSubject(subjectLine)
      setBody(generatedBody)

      if (contactMethod === 'whatsapp') {
        const number = phone.replace(/\D/g, '').replace(/^0/, '212')
        const url = new URL(`https://wa.me/${number}`)
        url.searchParams.set('text', externalMessage)
        externalWindow.location.href = url.toString()
        setSecureSendPending(false)
        setConfirmationExpiresAt(null)
        setConfirmationRequested(true)
        return
      }

      if (gmailStatus?.connected && gmailStatus?.draft_authorized) {
        const form = new FormData()
        form.append('recipient', recipient.trim())
        form.append('subject', subjectLine)
        form.append('body', generatedBody)
        form.append('cover_letter', coverLetter.trim())
        form.append('offer_title', poste.trim())
        form.append('offer_url', offerUrl.trim())
        form.append('offer_description', '')
        if (coverLetterFile) form.append('cover_letter_file', coverLetterFile)
        const response = await api.sendApplication(application.id, form)
        setConfirmationExpiresAt(response.expires_at)
        setSecureSendPending(true)
        setConfirmationRequested(true)
        return
      }

      const gmailUrl = new URL('https://mail.google.com/mail/')
      gmailUrl.searchParams.set('view', 'cm')
      gmailUrl.searchParams.set('fs', '1')
      gmailUrl.searchParams.set('to', recipient.trim())
      gmailUrl.searchParams.set('su', subjectLine)
      gmailUrl.searchParams.set('body', externalMessage)
      externalWindow.location.href = gmailUrl.toString()
      setSecureSendPending(false)
      setConfirmationExpiresAt(null)
      setConfirmationRequested(true)
    } catch (error) {
      if (externalWindow && !externalWindow.closed) externalWindow.close()
      setErr(error.message)
      if (application) setResult(application)
    } finally {
      setBusy(false)
    }
  }

  const retryDelivery = async () => {
    setErr('')
    const externalWindow = contactMethod === 'whatsapp' || !(gmailStatus?.connected && gmailStatus?.draft_authorized)
      ? window.open('', '_blank')
      : null
    if ((contactMethod === 'whatsapp' || !(gmailStatus?.connected && gmailStatus?.draft_authorized)) && !externalWindow) {
      setErr('Le navigateur a bloqué la fenêtre de contact. Autorisez les pop-ups puis réessayez.')
      return
    }
    setBusy(true)
    try {
      if (contactMethod === 'whatsapp') {
        const number = phone.replace(/\D/g, '').replace(/^0/, '212')
        const url = new URL(`https://wa.me/${number}`)
        const externalMessage = coverLetter.trim()
          ? `${body.trim()}\n\n--- Lettre de motivation ---\n${coverLetter.trim()}`
          : body.trim()
        url.searchParams.set('text', externalMessage)
        externalWindow.location.href = url.toString()
        setConfirmationRequested(true)
        setSecureSendPending(false)
        setConfirmationExpiresAt(null)
        return
      }
      if (gmailStatus?.connected && gmailStatus?.draft_authorized) {
        const form = new FormData()
        form.append('recipient', recipient.trim())
        form.append('subject', subject.trim())
        form.append('body', body.trim())
        form.append('cover_letter', coverLetter.trim())
        form.append('offer_title', poste.trim())
        form.append('offer_url', offerUrl.trim())
        form.append('offer_description', '')
        if (coverLetterFile) form.append('cover_letter_file', coverLetterFile)
        const response = await api.sendApplication(result.id, form)
        setConfirmationExpiresAt(response.expires_at)
        setSecureSendPending(true)
        setConfirmationRequested(true)
        return
      }
      const gmailUrl = new URL('https://mail.google.com/mail/')
      gmailUrl.searchParams.set('view', 'cm')
      gmailUrl.searchParams.set('fs', '1')
      gmailUrl.searchParams.set('to', recipient.trim())
      gmailUrl.searchParams.set('su', subject.trim())
      const externalMessage = coverLetter.trim()
        ? `${body.trim()}\n\n--- Lettre de motivation ---\n${coverLetter.trim()}`
        : body.trim()
      gmailUrl.searchParams.set('body', externalMessage)
      externalWindow.location.href = gmailUrl.toString()
      setConfirmationRequested(true)
      setSecureSendPending(false)
      setConfirmationExpiresAt(null)
    } catch (error) {
      if (externalWindow && !externalWindow.closed) externalWindow.close()
      setErr(error.message)
    } finally {
      setBusy(false)
    }
  }

  const markManualSendComplete = async () => {
    setBusy(true)
    setErr('')
    try {
      const updated = await updateTracking(result.id, { statut: 'Candidature envoyée' }, 'Candidature marquée comme envoyée')
      if (updated) setSent(true)
      else setErr('Impossible de mettre à jour le suivi. Réessayez.')
    } finally {
      setBusy(false)
    }
  }

  const input = 'mt-1.5 w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] font-normal outline-none focus:border-primary'
  const fieldError = (name) => fieldErrors[name] && <p role="alert" className="mt-1 text-[12px] font-normal text-red-600">{fieldErrors[name]}</p>
  const updateField = (name, setter) => (event) => {
    setter(event.target.value)
    setFieldErrors((current) => ({ ...current, [name]: '' }))
  }

  return (
    <Modal title={sent ? 'Candidature envoyée' : 'Postuler'} onClose={onClose}>
      {result ? (
        <div className="space-y-4">
          <p className="text-[14px] text-muted">{poste} · {ent}</p>
          {busy && !confirmationRequested ? (
            <p role="status" className="text-[14px] text-muted">Envoi de votre candidature en cours…</p>
          ) : sent ? (
            <p role="status" className="rounded-xl border border-success/30 bg-success-soft p-4 text-success">Votre candidature a bien été envoyée.</p>
          ) : confirmationRequested ? (
            <div className="space-y-3 rounded-xl border border-success/30 bg-success-soft p-4 text-[13px]">
              <p className="font-semibold text-success">{secureSendPending ? `Un e-mail de confirmation a été envoyé à ${gmailStatus?.sender || 'votre compte Gmail'}.` : `Votre message est prêt dans ${contactMethod === 'whatsapp' ? 'WhatsApp' : 'Gmail'}.`}</p>
              <p>{secureSendPending
                ? 'Confirmez l’envoi depuis l’e-mail reçu. BookJob actualisera ensuite le suivi.'
                : contactMethod === 'whatsapp'
                  ? `Vérifiez le message et ajoutez votre CV${coverLetterFile ? ' et votre lettre' : ''} dans WhatsApp avant l’envoi.`
                  : `Vérifiez le message et ajoutez votre CV${coverLetterFile ? ' et votre lettre' : ''} si besoin, puis envoyez-le.`}</p>
              {secureSendPending && confirmationExpiresAt && (
                <p>Lien valable jusqu’à {new Date(confirmationExpiresAt * 1000).toLocaleTimeString()}.</p>
              )}
              {!secureSendPending && (
                <button type="button" disabled={busy} className="btn-outline" onClick={markManualSendComplete}>
                  {busy ? 'Mise à jour…' : 'Confirmer que je l’ai envoyée'}
                </button>
              )}
              {err && <p role="alert" className="text-red-600">{err}</p>}
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-[14px]">La candidature est enregistrée, mais l’envoi n’a pas abouti.</p>
              {err && <p role="alert" className="text-[13px] text-red-600">{err}</p>}
              <button type="button" disabled={busy} onClick={retryDelivery} className="btn-primary">
                {busy ? 'Envoi en cours…' : 'Envoyer ma candidature'}
              </button>
            </div>
          )}
          <button type="button" onClick={onClose} className="btn-outline">Fermer</button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <p className="text-[14px] text-muted">{poste} · {ent || 'Entreprise à préciser'}</p>
          {!company?.id && (
            <label className="block text-[13px] font-semibold">Entreprise
              <input value={ent} onChange={updateField('ent', setEnt)} className={input} />
              {fieldError('ent')}
            </label>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-[13px] font-semibold">Nom et prénom *
              <input autoComplete="name" value={candidateName} onChange={updateField('candidateName', setCandidateName)} className={input} />
              {fieldError('candidateName')}
            </label>
            <label className="block text-[13px] font-semibold">E-mail *
              <input type="email" autoComplete="email" value={candidateEmail} onChange={updateField('candidateEmail', setCandidateEmail)} className={input} />
              {fieldError('candidateEmail')}
            </label>
            <label className="block text-[13px] font-semibold">Téléphone *
              <input type="tel" autoComplete="tel" value={candidatePhone} onChange={updateField('candidatePhone', setCandidatePhone)} className={input} />
              {fieldError('candidatePhone')}
            </label>
            <label className="block text-[13px] font-semibold">Ville
              <input autoComplete="address-level2" value={candidateCity} onChange={updateField('candidateCity', setCandidateCity)} className={input} />
            </label>
          </div>
          <label className="block text-[13px] font-semibold">Poste visé
            <input value={poste} onChange={updateField('poste', setPoste)} className={input} />
            {fieldError('poste')}
          </label>
          {contactMethod === 'email' ? (
            <label className="block text-[13px] font-semibold">E-mail du recruteur *
              <input type="email" value={recipient} onChange={(event) => {
                recipientTouched.current = true
                setRecipient(event.target.value)
                setSelectedEmailSource('')
                setFieldErrors((current) => ({ ...current, recipient: '' }))
              }} className={input} placeholder="recrutement@entreprise.ma" />
              {fieldError('recipient')}
            </label>
          ) : (
            <label className="block text-[13px] font-semibold">Téléphone / WhatsApp de l’entreprise *
              <input type="tel" value={phone} onChange={updateField('phone', setPhone)} className={input} placeholder="+212 6 00 00 00 00" />
              {fieldError('phone')}
            </label>
          )}
          {contactMethod === 'email' && emailLookupStatus && <p role="status" className="text-[12px] text-muted">{emailLookupStatus}</p>}
          {contactMethod === 'email' && contactEmails.length > 0 && (
            <div className="text-[12px] text-muted">
              Adresses trouvées : {contactEmails.map((item) => (
                <button key={`${item.email}-${item.source}`} type="button" onClick={() => {
                  recipientTouched.current = true
                  setRecipient(item.email)
                  setSelectedEmailSource(item.source)
                }} className="ml-1 text-primary underline">{item.email}</button>
              ))}
              {selectedEmailSource && <a href={selectedEmailSource} target="_blank" rel="noreferrer" className="ml-2 underline">Source</a>}
            </div>
          )}
          <div>
            <label className="block text-[13px] font-semibold">CV * <span className="font-normal text-muted">(PDF uniquement · 5 Mo max)</span>
              {cvs.length > 0 && !file && (
                <select value={cvId} onChange={(event) => {
                  setCvId(event.target.value)
                  setFieldErrors((current) => ({ ...current, cv: '' }))
                }} className={input}>
                  <option value="">Choisir un CV enregistré</option>
                  {cvs.map((cv) => <option key={cv.id} value={cv.id}>{cv.name}{cv.main ? ' (principal)' : ''}</option>)}
                </select>
              )}
              <input ref={ref} type="file" accept=".pdf,application/pdf" onChange={(event) => {
                setFile(event.target.files?.[0] || null)
                setFieldErrors((current) => ({ ...current, cv: '' }))
              }} className={input} />
            </label>
            {file && <button type="button" onClick={() => { setFile(null); if (ref.current) ref.current.value = '' }} className="mt-1 text-[12px] text-primary underline">Retirer {file.name}</button>}
            {fieldError('cv')}
          </div>
          <div>
            <label className="block text-[13px] font-semibold">Lettre de motivation <span className="font-normal text-muted">(facultative)</span>
              <textarea rows={3} value={coverLetter} onChange={(event) => {
                setCoverLetter(event.target.value)
                if (event.target.value && coverLetterFile) {
                  setCoverLetterFile(null)
                  if (letterRef.current) letterRef.current.value = ''
                }
              }} className={input} placeholder="Vous pouvez saisir votre lettre ici." />
              <input ref={letterRef} type="file" accept=".pdf,application/pdf" onChange={(event) => {
                const nextFile = event.target.files?.[0] || null
                setCoverLetterFile(nextFile)
                if (nextFile) setCoverLetter('')
                setFieldErrors((current) => ({ ...current, coverLetter: '' }))
              }} className={input} />
            </label>
            {coverLetterFile && <button type="button" onClick={() => { setCoverLetterFile(null); if (letterRef.current) letterRef.current.value = '' }} className="mt-1 text-[12px] text-primary underline">Retirer {coverLetterFile.name}</button>}
            {fieldError('coverLetter')}
          </div>
          <label className="block text-[13px] font-semibold">Message au recruteur <span className="font-normal text-muted">(facultatif)</span>
            <textarea rows={3} value={body} onChange={updateField('body', setBody)} className={input} placeholder="Ajoutez un message personnel, si vous le souhaitez." />
          </label>
          <label className="flex items-start gap-2 text-[12px] font-normal text-muted">
            <input type="checkbox" checked={consent} onChange={(event) => {
              setConsent(event.target.checked)
              setFieldErrors((current) => ({ ...current, consent: '' }))
            }} className="mt-0.5" />
            <span>J’accepte l’utilisation de mes données et la transmission de mon dossier au recruteur.</span>
          </label>
          {fieldError('consent')}
          {err && <p role="alert" className="text-[13px] text-red-600">{err}</p>}
          <div className="flex justify-end pt-1">
            <button type="submit" disabled={busy} className="btn-primary">{busy ? 'Envoi en cours…' : 'Envoyer ma candidature'}</button>
          </div>
        </form>
      )}
    </Modal>
  )
}
