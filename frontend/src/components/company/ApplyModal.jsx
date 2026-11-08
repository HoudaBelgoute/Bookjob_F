import { BriefcaseBusiness, Check, Mail, MessageCircle, Send, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, cvUrl } from '../../api'
import Modal from '../ui/Modal'
import { useStore } from '../../store/useStore'

export default function ApplyModal({ company, onClose, onDone }) {
  const { cvs, sendApplication, applicationSendStatus, refreshTracking, refreshCvs, notify, tracking, profile, meta } = useStore()
  const existing = company?.id ? tracking.find((t) => t.id === company.id) : null
  const [ent, setEnt] = useState(company?.short || '')
  const [poste, setPoste] = useState(existing?.poste || 'Stage PFE / Data-IT')
  const [goal, setGoal] = useState('stage')
  const [contactMethod, setContactMethod] = useState('email')
  const [phone, setPhone] = useState(company?.telephone || '')
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
  const [contactUrl, setContactUrl] = useState('')
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
    if (contactMethod === 'email' && recipient.trim()) f.append('email', recipient.trim())
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
      setBody(contactMethod === 'whatsapp'
        ? `Bonjour,\n\nJe vous contacte pour vous proposer ma candidature (${poste || 'candidature spontanée'}) auprès de ${ent}. Je serais ravi(e) d’échanger avec vous et de vous transmettre mon CV.\n\n${profile.nom || ''}${profile.tel ? `\n${profile.tel}` : ''}`
        : `Bonjour,\n\nJe vous adresse ma candidature pour ${poste || 'un stage'} au sein de ${ent}. Vous trouverez mon CV et ma lettre de motivation en pièces jointes.\n\nJe reste à votre disposition pour tout complément d'information ou un entretien.\n\nCordialement,\n${profile.nom || ''}${profile.email ? `\n${profile.email}` : ''}${profile.tel ? `\n${profile.tel}` : ''}`)
      setResult(r)
      onDone?.(r)
      if (contactMethod === 'email') {
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
  }

  const connectGmail = () => {
    const popup = window.open('/api/google/connect', 'bookjob-google-oauth', 'popup,width=520,height=680')
    if (!popup) setErr('Le navigateur a bloqué la fenêtre Google. Autorise les pop-ups puis réessaie.')
  }

  const requestContactConfirmation = () => {
    setErr('')
    if (contactMethod === 'whatsapp') {
      const number = phone.replace(/\D/g, '').replace(/^0/, '212')
      if (number.length < 8) {
        setErr('Saisis un numéro de téléphone valide pour contacter l’entreprise sur WhatsApp.')
        return
      }
      if (!body.trim()) {
        setErr('Vérifie ton message avant d’ouvrir WhatsApp.')
        return
      }
      const url = new URL(`https://wa.me/${number}`)
      url.searchParams.set('text', body.trim())
      const whatsappWindow = window.open(url.toString(), '_blank')
      if (!whatsappWindow) {
        setErr('Le navigateur a bloqué WhatsApp. Autorise les pop-ups puis réessaie.')
        return
      }
      setContactUrl(url.toString())
      setConfirmationRequested(true)
      setConfirmationExpiresAt(null)
      return
    }
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

  const input = 'mt-1.5 w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] font-normal outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10'
  return (
    <Modal title={result ? (sent ? 'Candidature envoyée' : 'Vérifier et envoyer') : 'L’atelier des candidatures'} onClose={onClose} wide>
      {result ? (
        <div className="space-y-4">
          {sent ? (
            <div role="status" className="rounded-xl border border-success/30 bg-success-soft p-4 text-success">
              Candidature envoyée {contactMethod === 'whatsapp' ? `à ${phone}` : `à ${recipient}`}. La relance est planifiée dans 7 jours.
            </div>
          ) : confirmationRequested ? (
            <div className="space-y-3 rounded-xl border border-success/30 bg-success-soft p-4">
              <p className="font-semibold text-success">
                {contactMethod === 'whatsapp' ? 'WhatsApp a été ouvert avec le numéro et le message préremplis.' : 'Gmail a été ouvert avec le destinataire, l’objet et le message préremplis.'}
              </p>
              <p className="text-[13px]">
                {contactMethod === 'whatsapp'
                  ? 'La candidature n’a pas encore été envoyée. Vérifie le message dans WhatsApp puis confirme toi-même son envoi.'
                  : 'La candidature n’a pas encore été envoyée. Dans Gmail, joins ton CV et, si nécessaire, ta lettre de motivation, puis clique toi-même sur « Envoyer ». BookJob ne peut pas joindre automatiquement les fichiers via le lien du navigateur.'}
              </p>
              <button type="button" className="btn-outline" onClick={() => window.open(contactMethod === 'whatsapp' ? contactUrl : `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(recipient.trim())}&su=${encodeURIComponent(subject.trim())}&body=${encodeURIComponent(body.trim())}`, '_blank', 'noopener,noreferrer')}>
                {contactMethod === 'whatsapp' ? 'Rouvrir WhatsApp' : 'Rouvrir Gmail'}
              </button>
              {err && <p role="alert" className="text-[13px] text-red-600">{err}</p>}
            </div>
          ) : (
            <>
              <div className="rounded-xl border border-gold/30 bg-gold-soft p-4">
                <p className="font-semibold text-gold-ink">Aucun message n’a encore été envoyé.</p>
                <p className="mt-1 text-[13px] text-gold-ink">Vérifie le destinataire, le message et ton CV avant de continuer. L’envoi sera confirmé dans {contactMethod === 'whatsapp' ? 'WhatsApp' : 'Gmail'}.</p>
              </div>
              {result.fichier_cv && <a href={cvUrl(result.id)} target="_blank" rel="noreferrer" className="block text-[13px] font-semibold text-primary underline">Vérifier ou télécharger le CV joint</a>}
              {contactMethod === 'whatsapp' ? (
                <label className="block text-[13px] font-semibold">Numéro WhatsApp de l’entreprise
                  <input type="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} className={input} />
                </label>
              ) : (
                <>
                  <label className="block text-[13px] font-semibold">Adresse e-mail du destinataire
                    <input type="email" required value={recipient} onChange={(e) => setRecipient(e.target.value)} className={input} />
                  </label>
                  {selectedEmailSource && <p className="text-[12px] text-muted">Adresse trouvée sur le site officiel : <a href={selectedEmailSource} target="_blank" rel="noreferrer" className="underline">vérifier la source</a></p>}
                  <label className="block text-[13px] font-semibold">Objet
                    <input required value={subject} onChange={(e) => setSubject(e.target.value)} className={input} />
                  </label>
                </>
              )}
              <label className="block text-[13px] font-semibold">Message
                <textarea required rows={8} value={body} onChange={(e) => setBody(e.target.value)} className={input} />
              </label>
              {contactMethod === 'email' && <label className="block text-[13px] font-semibold">Lettre de motivation (jointe comme fichier texte)
                <textarea rows={10} value={coverLetter} onChange={(e) => setCoverLetter(e.target.value)} className={input} placeholder={generatingLetter ? 'Génération de la lettre…' : 'Écris ou colle ta lettre de motivation ici.'} />
              </label>}
              {contactMethod === 'email' && <div className="text-[13px] font-semibold">
                Fichier de lettre finalisé (facultatif, à joindre manuellement dans Gmail)
                <input ref={letterRef} type="file" accept=".pdf" className="sr-only" onChange={(e) => setCoverLetterFile(e.target.files?.[0] || null)} />
                <div className="mt-2 flex items-center gap-3">
                  <button type="button" className="btn-outline !py-2" onClick={() => letterRef.current?.click()}>
                    {coverLetterFile ? 'Changer le fichier' : 'Importer la lettre'}
                  </button>
                  <span className="truncate text-[12px] font-normal text-muted">{coverLetterFile ? coverLetterFile.name : 'PDF uniquement, 5 Mo max'}</span>
                  {coverLetterFile && <button type="button" className="text-[12px] underline" onClick={() => setCoverLetterFile(null)}>Retirer</button>}
                </div>
              </div>}
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
            {!sent && !confirmationRequested && <button type="button" disabled={busy || generatingLetter || !body.trim() || (contactMethod === 'email' && (!recipient || !subject.trim()))} onClick={requestContactConfirmation} className="btn-primary">{busy ? 'Ouverture…' : contactMethod === 'whatsapp' ? 'Ouvrir WhatsApp' : 'Ouvrir Gmail'}</button>}
          </div>
        </div>
      ) : (
      <form onSubmit={submit} className="space-y-5">
        <section className="relative overflow-hidden rounded-[24px] border border-line bg-[#f7f5eb] p-6 sm:p-8">
          <div className="relative z-10 max-w-2xl">
            <p className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.18em] text-gold-ink"><Send size={14} /> L’atelier des candidatures</p>
            <h2 className="mt-3 font-serif text-[32px] leading-[1.08] tracking-tight text-primary sm:text-[42px]">Votre prochain chapitre commence ici.</h2>
            <p className="mt-3 max-w-xl text-[14px] leading-relaxed text-muted">Un message qui vous ressemble, les bons documents et une candidature prête à partir.</p>
            <p className="mt-4 inline-flex max-w-full border-b-2 border-gold pb-1 text-[13px] font-bold text-primary">{ent || 'Votre entreprise cible'} · {poste}</p>
          </div>
          <div aria-hidden="true" className="pointer-events-none absolute -right-4 -top-5 hidden h-52 w-64 items-center justify-center sm:flex">
            <div className="absolute h-36 w-44 rotate-[-8deg] rounded-2xl border-2 border-primary bg-white p-4 shadow-lg">
              <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-soft text-primary"><BriefcaseBusiness size={20} /></span><span className="space-y-2"><i className="block h-2 w-20 rounded bg-gold/60" /><i className="block h-2 w-14 rounded bg-line" /></span></div>
              <i className="mt-4 block h-2 w-32 rounded bg-line" /><i className="mt-2 block h-2 w-24 rounded bg-line" />
            </div>
            <span className="absolute bottom-5 right-16 flex h-16 w-20 items-center justify-center rounded-xl border-2 border-primary bg-[#e6a1ac] text-primary shadow-md"><Mail size={34} /></span>
            <span className="absolute bottom-4 left-6 flex h-10 w-10 items-center justify-center rounded-full bg-success text-white shadow"><Check size={24} /></span>
            <Sparkles size={24} className="absolute right-8 top-8 text-gold" />
          </div>
        </section>

        <div className="grid gap-4 md:grid-cols-2">
          <section className="rounded-2xl border border-line border-t-[3px] border-t-gold bg-white p-5 sm:p-6">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted">01 / Le contact</p>
            <h3 className="mt-3 text-[16px] font-bold text-primary">Comment souhaitez-vous contacter l’entreprise ?</h3>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" onClick={() => setContactMethod('email')} aria-pressed={contactMethod === 'email'} className={`inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-[13px] font-semibold transition-all ${contactMethod === 'email' ? 'border-primary bg-primary text-white shadow-card' : 'border-line bg-white text-ink hover:border-primary hover:bg-primary-soft'}`}><Mail size={17} /> Contacter via E-mail</button>
              <button type="button" onClick={() => setContactMethod('whatsapp')} aria-pressed={contactMethod === 'whatsapp'} className={`inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-[13px] font-semibold transition-all ${contactMethod === 'whatsapp' ? 'border-primary bg-primary text-white shadow-card' : 'border-line bg-white text-ink hover:border-primary hover:bg-primary-soft'}`}><MessageCircle size={17} /> Contacter via WhatsApp</button>
            </div>
          </section>
          <section className="rounded-2xl border border-line border-t-[3px] border-t-[#dc8796] bg-white p-5 sm:p-6">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted">02 / Votre objectif</p>
            <label className="mt-3 block text-[16px] font-bold text-primary" htmlFor="application-goal">Que recherchez-vous ?</label>
            <select id="application-goal" value={goal} onChange={(e) => {
              const nextGoal = e.target.value
              setGoal(nextGoal)
              setPoste(nextGoal === 'emploi' ? 'Emploi' : nextGoal === 'spontanee' ? 'Candidature spontanée' : 'Stage PFE / Data-IT')
            }} className={input}>
              <option value="stage">Stage / PFE</option>
              <option value="emploi">Emploi</option>
              <option value="spontanee">Candidature spontanée</option>
            </select>
            <p className="mt-2 text-[12px] text-muted">Ce choix personnalise votre message et votre candidature.</p>
          </section>
        </div>

        {contactMethod === 'email' && <section className="rounded-2xl border border-line bg-white p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary"><Mail size={22} /></span>
              <div>
                <h3 className="text-[17px] font-bold">Connectez votre Gmail pour postuler</h3>
                <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-muted">
                  {gmailStatus?.connected ? `Gmail est connecté${gmailStatus.sender ? ` (${gmailStatus.sender})` : ''}. ` : ''}
                  Choisissez le compte qui enverra votre candidature. Vous gardez le contrôle et confirmez vous-même l’envoi dans Gmail.
                </p>
              </div>
            </div>
            <button type="button" onClick={connectGmail} className="btn-outline shrink-0">
              {gmailStatus?.connected ? 'Choisir un autre Gmail' : 'Connecter mon Gmail'}
            </button>
          </div>
          {!gmailStatus?.configured && <p className="mt-3 rounded-lg bg-gold-soft px-3 py-2 text-[12px] text-gold-ink">La connexion Gmail n’est pas configurée sur ce serveur. Vous pourrez tout de même ouvrir un brouillon dans votre compte Gmail.</p>}
        </section>}

        <section className="rounded-2xl border border-line bg-white p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted">03 / Votre dossier</p>
              <h3 className="mt-1 text-[17px] font-bold">Préparez les informations de candidature</h3>
            </div>
            <span className="rounded-full bg-primary-soft px-3 py-1 text-[11px] font-bold text-primary">Étape 1 sur 2</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-[13px] font-semibold">
              Entreprise
              <input value={ent} onChange={(e) => setEnt(e.target.value)} className={input} readOnly={!!company?.id} />
            </label>
            <label className="block text-[13px] font-semibold">
              Poste visé
              <input value={poste} onChange={(e) => setPoste(e.target.value)} className={input} />
            </label>
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
        {contactMethod === 'email' ? (
          <label className="block text-[13px] font-semibold">E-mail de l’entreprise (facultatif)
            <input type="email" value={recipient} onChange={(e) => {
              recipientTouched.current = true
              setRecipient(e.target.value)
              setSelectedEmailSource('')
            }} className={input} placeholder="recrutement@entreprise.ma" />
          </label>
        ) : (
          <label className="block text-[13px] font-semibold">Téléphone / WhatsApp de l’entreprise
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} className={input} placeholder="+212 6 00 00 00 00" />
          </label>
        )}
        {contactMethod === 'email' && emailLookupStatus && <p role="status" className="text-[12px] text-muted">{emailLookupStatus}</p>}
        {contactMethod === 'email' && contactEmails.length > 0 && (
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
        {contactMethod === 'email' && selectedEmailSource && <p className="text-[11px] text-muted">Source sélectionnée : <a href={selectedEmailSource} target="_blank" rel="noreferrer" className="underline">page officielle</a></p>}
        {err && <p role="alert" className="text-[13px] text-red-600">{err}</p>}
        <div className="flex justify-end gap-3 pt-1">
          <button type="button" onClick={onClose} className="btn-outline">Annuler</button>
          <button type="submit" disabled={busy} className="btn-primary"><Send size={16} />{busy ? 'Préparation…' : 'Préparer ma candidature'}</button>
        </div>
        </section>
      </form>
      )}
    </Modal>
  )
}
