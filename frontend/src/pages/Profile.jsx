import { Camera, Check, Download, FileText, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { libCvUrl } from '../api'
import UserAvatar from '../components/ui/UserAvatar'
import { useStore } from '../store/useStore'

const field = 'w-full rounded-xl border border-line px-3.5 py-2.5 text-[14px] outline-none focus:border-primary'

function Section({ id, title, sub, children, action }) {
  return (
    <section id={id} className="card p-6">
      <div className="flex items-start justify-between">
        <div><h2 className="text-[22px] font-normal">{title}</h2><p className="mt-1 text-[13px] text-muted">{sub}</p></div>
        {action}
      </div>
      <div className="mt-4 border-t border-line pt-4">{children}</div>
    </section>
  )
}

// Section texte libre modifiable (formation, expériences, projets, langues, certifications, résumé).
function TextSection({ id, field: key, title, sub, hint, rows = 4 }) {
  const { profile, saveProfile } = useStore()
  const [edit, setEdit] = useState(false)
  const [val, setVal] = useState(profile[key] || '')
  const save = async () => {
    if (await saveProfile({ [key]: val })) setEdit(false)
  }
  return (
    <Section id={id} title={title} sub={sub} action={!edit && <button onClick={() => { setVal(profile[key] || ''); setEdit(true) }} className="text-[13px] font-semibold text-primary">{profile[key] ? 'Modifier' : '+ Ajouter'}</button>}>
      {edit ? (
        <div>
          <textarea value={val} onChange={(e) => setVal(e.target.value)} rows={rows} aria-label={title} placeholder={hint} className={field} />
          <div className="mt-3 flex gap-3"><button className="btn-primary !py-2.5" onClick={save}>Enregistrer</button><button className="btn-outline !py-2.5" onClick={() => setEdit(false)}>Annuler</button></div>
        </div>
      ) : profile[key] ? (
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-muted">{profile[key]}</p>
      ) : (
        <p className="text-[14px] text-muted">Non renseigné.</p>
      )}
    </Section>
  )
}

function CvSection() {
  const { cvs, uploadCv, mainCv, removeCv, notify } = useStore()
  const fileRef = useRef(null)
  const [busy, setBusy] = useState(false)

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!/\.pdf$/i.test(file.name)) return notify('Format non pris en charge : PDF uniquement')
    if (file.size > 5 * 1024 * 1024) return notify('Fichier trop volumineux (5 Mo maximum)')
    setBusy(true)
    await uploadCv(file)
    setBusy(false)
  }

  return (
    <section className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[22px] font-normal">Mon CV prêt à postuler</h2>
          <p className="mt-1 text-[13px] text-muted">Importez votre CV une fois : il sera disponible lors de l’enregistrement de vos candidatures.</p>
        </div>
        <input ref={fileRef} type="file" accept=".pdf" className="sr-only" onChange={onFile} />
        <button type="button" className="btn-primary !py-2.5" disabled={busy} onClick={() => fileRef.current?.click()}>
          <Upload size={16} /> {busy ? 'Importation…' : 'Importer un CV'}
        </button>
      </div>
      {cvs.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-line px-4 py-6 text-center">
          <FileText className="mx-auto text-muted" size={24} />
          <p className="mt-2 text-[13px] text-muted">Aucun CV importé. Formats acceptés : PDF ou Word, 5 Mo maximum.</p>
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {cvs.map((cv) => (
            <li key={cv.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
              <FileText className="shrink-0 text-primary" size={20} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14px] font-medium">
                  {cv.name}
                  {cv.main && <span className="ml-2 rounded-md bg-success-soft px-2 py-0.5 text-[11px] font-semibold text-success">Principal</span>}
                </p>
                <p className="text-[12px] text-muted">{(cv.size / 1024).toFixed(0)} Ko · {cv.file.split('.').pop().toUpperCase()}</p>
              </div>
              {!cv.main && <button type="button" className="btn-outline !px-3 !py-2 text-[12px]" onClick={() => mainCv(cv.id)}>Définir principal</button>}
              <a className="btn-outline !px-3 !py-2" href={libCvUrl(cv.id)} aria-label={`Télécharger ${cv.name}`}><Download size={16} /></a>
              <button type="button" aria-label={`Supprimer ${cv.name}`} className="rounded-lg p-2 text-red-600 hover:bg-red-50" onClick={() => window.confirm('Supprimer ce CV ?') && removeCv(cv.id)}><Trash2 size={17} /></button>
            </li>
          ))}
        </ul>
      )}
      {cvs.length > 0 && <p className="mt-3 text-[12px] text-muted">Le CV principal est présélectionné dans le formulaire de candidature.</p>}
    </section>
  )
}

// Photo de profil : importée par l'utilisateur (PNG, JPG ou WebP, 2 Mo maximum).
function AvatarPicker() {
  const { profile, avatarUrl, uploadAvatar, removeAvatar, notify } = useStore()
  const fileRef = useRef(null)
  const [busy, setBusy] = useState(false)

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!/^image\/(png|jpe?g|webp)$/.test(file.type) && !/\.(png|jpe?g|webp)$/i.test(file.name)) return notify('Format non pris en charge : PNG, JPG ou WebP')
    if (file.size > 2 * 1024 * 1024) return notify('Image trop volumineuse (2 Mo maximum)')
    setBusy(true)
    await uploadAvatar(file)
    setBusy(false)
  }

  return (
    <div className="relative shrink-0">
      <UserAvatar name={profile.nom} url={avatarUrl} className="h-[100px] w-[100px] rounded-2xl bg-primary-soft text-[34px]" />
      <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={onFile} aria-label="Importer une photo de profil" />
      <button
        type="button"
        disabled={busy}
        onClick={() => fileRef.current?.click()}
        aria-label={avatarUrl ? 'Changer ma photo de profil' : 'Ajouter une photo de profil'}
        title={avatarUrl ? 'Changer la photo' : 'Ajouter une photo'}
        className="absolute -bottom-2 -right-2 flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-primary text-white shadow-card hover:bg-primary-hover disabled:opacity-50"
      >
        <Camera size={16} />
      </button>
      {avatarUrl && (
        <button
          type="button"
          disabled={busy}
          onClick={() => window.confirm('Supprimer ta photo de profil ?') && removeAvatar()}
          aria-label="Supprimer ma photo de profil"
          title="Supprimer la photo"
          className="absolute -left-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-white text-red-600 shadow-card hover:bg-red-50 disabled:opacity-50"
        >
          <Trash2 size={13} />
        </button>
      )}
    </div>
  )
}

export default function Profile() {
  const { profile, skills, completion, saveProfile } = useStore()
  const [info, setInfo] = useState(null)
  const [skill, setSkill] = useState('')

  const addSkill = async (e) => {
    e.preventDefault()
    const s = skill.trim()
    if (!s || skills.some((x) => x.toLowerCase() === s.toLowerCase())) return setSkill('')
    await saveProfile({ competences: [...skills, s].join(', ') })
    setSkill('')
  }
  const removeSkill = (s) => saveProfile({ competences: skills.filter((x) => x !== s).join(', ') })
  const saveInfo = async (e) => {
    e.preventDefault()
    if (await saveProfile(info)) setInfo(null)
  }
  const F = (k, label, type = 'text') => (
    <label className="block text-[13px] font-semibold">{label}<input type={type} value={info[k] || ''} onChange={(e) => setInfo({ ...info, [k]: e.target.value })} className={`${field} mt-1.5 font-normal`} /></label>
  )
  const todo = completion.items.filter((i) => !i.done)

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <div className="h-[140px] rounded-t-3xl bg-gradient-to-r from-navy-900 to-navy-600 md:h-[170px]" />
      <div className="card relative -mt-[60px] mx-0 flex flex-wrap items-center gap-5 p-6 md:mx-9">
        <AvatarPicker />
        <div className="min-w-0 flex-1">
          <h1 className="text-[30px] font-normal">{profile.nom || 'Votre nom'}</h1>
          <p className="text-[14px] text-muted">{[profile.titre, profile.ville].filter(Boolean).join(' · ') || 'Complétez votre profil'}</p>
          <p className="text-[13px] text-muted">{[profile.email, profile.tel, profile.linkedin].filter(Boolean).join(' · ')}</p>
        </div>
        <button className="btn-outline" onClick={() => setInfo({ ...profile })}>Modifier mes informations</button>
      </div>

      {info && (
        <form onSubmit={saveInfo} className="card mt-5 grid gap-4 p-6 md:grid-cols-2">
          {F('nom', 'Nom complet')}{F('titre', 'Intitulé visé (ex. Stagiaire Data Analyst)')}{F('email', 'E-mail', 'email')}{F('tel', 'Téléphone', 'tel')}{F('ville', 'Ville')}{F('linkedin', 'LinkedIn / GitHub')}
          <div className="flex gap-3 md:col-span-2"><button className="btn-primary !py-2.5">Enregistrer</button><button type="button" className="btn-outline !py-2.5" onClick={() => setInfo(null)}>Annuler</button></div>
        </form>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <CvSection />
          <TextSection id="resume" field="resume" title="À propos" sub="Votre présentation professionnelle (utilisée dans le CV)." hint="Ex. Étudiant en data analyse, je cherche un stage PFE à Marrakech…" />
          <TextSection id="formation" field="formation" title="Formation" sub="Une ligne par diplôme : année – diplôme – école." rows={4} />
          <TextSection id="experiences" field="experiences" title="Expériences" sub="Poste – structure – période – missions." rows={5} />
          <TextSection id="projets" field="projets" title="Projets / portfolio" sub="Titre, technologies, résultats, lien GitHub." rows={5} />
          <TextSection id="langues" field="langues" title="Langues" sub="Séparées par des virgules." rows={2} />
          <TextSection id="certifs" field="certifs" title="Certifications" sub="Nom – organisme – date." rows={3} />
        </div>

        <div className="space-y-5">
          {completion.percent < 100 && <section className="card p-6">
            <div className="flex items-center justify-between"><h2 className="text-[22px] font-normal">Complétion</h2><span className="text-[28px] font-light text-primary">{completion.percent}%</span></div>
            <div className="mt-3 h-2 rounded-full bg-chip"><div className="h-full rounded-full bg-gold" style={{ width: `${completion.percent}%` }} /></div>
            <p className="mt-4 text-[12px] text-muted">{todo.length ? `Encore ${todo.length} section(s) à renseigner.` : 'Profil complet.'}</p>
            <ul className="mt-3 space-y-3">
              {completion.items.map((c) => (
                <li key={c.field} className="flex items-center gap-3 text-[13px]">
                  {c.done ? <Check size={18} className="text-success" /> : <span className="h-[18px] w-[18px] rounded-full border border-[#c5cedc]" />}
                  <span className={c.done ? 'text-primary' : 'text-muted'}>{c.label}</span>
                </li>
              ))}
            </ul>
          </section>}

          <section className="card p-6">
            <h2 className="text-[22px] font-normal">Compétences</h2>
            <div className="mt-4 flex flex-wrap gap-2.5">
              {skills.length === 0 && <p className="text-[13px] text-muted">Aucune compétence.</p>}
              {skills.map((s) => (
                <button key={s} onClick={() => removeSkill(s)} title="Cliquer pour retirer" className="tag !px-3.5 !py-1.5 !text-[13px] hover:bg-red-50 hover:text-red-600">{s}</button>
              ))}
            </div>
            <form onSubmit={addSkill} className="mt-4 flex gap-2">
              <input value={skill} onChange={(e) => setSkill(e.target.value)} placeholder="Ajouter une compétence" aria-label="Ajouter une compétence" className="min-w-0 flex-1 rounded-xl border border-line px-3 py-2 text-[13px] outline-none focus:border-primary" />
              <button className="btn-soft !py-2">Ajouter</button>
            </form>
          </section>
        </div>
      </div>
    </div>
  )
}
