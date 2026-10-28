import clsx from 'clsx'
import { Download, Mail, Printer, Sparkles, Trash2, Upload } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, libCvUrl } from '../api'
import { fmtDate, mdToHtml } from '../data/data'
import { useStore } from '../store/useStore'

const TEMPLATES = {
  Classique: 'font-family:Georgia,serif;color:#111',
  Moderne: 'font-family:Inter,Arial,sans-serif;color:#0f2444',
  Compact: 'font-family:Arial,sans-serif;font-size:12px;color:#111',
}
const PREVIEW = {
  Classique: { fontFamily: 'Georgia,serif', color: '#111' },
  Moderne: { fontFamily: 'Inter,Arial,sans-serif', color: '#0f2444' },
  Compact: { fontFamily: 'Arial,sans-serif', fontSize: 12, color: '#111' },
}
const field = 'mt-1.5 w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] font-normal outline-none focus:border-primary'

function printHtml(title, md, tpl) {
  const w = window.open('', '_blank')
  if (!w) return
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${title}</title><style>body{${TEMPLATES[tpl]};max-width:760px;margin:30px auto;line-height:1.45}h1{font-size:24px;margin:0}h2{font-size:15px;border-bottom:1px solid #ccc;margin-top:18px;text-transform:uppercase;letter-spacing:.05em}p{margin:4px 0}</style></head><body>${mdToHtml(md)}</body></html>`)
  w.document.close()
  w.focus()
  w.print()
}

function download(name, text) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function CvStudio() {
  const { cvs, uploadCv, mainCv, removeCv, allCompanies, meta, profile, completion, tracking, notify } = useStore()
  const [params] = useSearchParams()
  const [tab, setTab] = useState(params.get('company') ? 'gen' : 'mine')
  const fileRef = useRef(null)

  const onFile = (e) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    if (!/\.pdf$/i.test(f.name)) return notify('Format non pris en charge : PDF uniquement')
    if (f.size > 5 * 1024 * 1024) return notify('Fichier trop volumineux (5 Mo maximum)')
    uploadCv(f)
  }

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-8 md:px-8">
      <p className="eyebrow">Documents</p>
      <h1 className="page-title mt-3">CV Studio</h1>
      <p className="mt-3 text-[16px] text-muted">Importez vos CV, ou générez un CV et un e-mail adaptés à une entreprise à partir de votre profil.</p>

      <div className="mt-6 inline-flex rounded-xl bg-chip p-1">
        {[['mine', 'J’ai déjà un CV'], ['gen', 'Générer CV + e-mail'], ['letter', 'Lettre de motivation']].map(([v, l]) => (
          <button key={v} onClick={() => setTab(v)} className={clsx('rounded-lg px-4 py-2 text-[14px]', tab === v ? 'bg-white font-medium shadow-card' : 'text-muted')}>{l}</button>
        ))}
      </div>

      {tab === 'mine' && (
        <section className="mt-6">
          <input ref={fileRef} type="file" accept=".pdf" className="sr-only" onChange={onFile} />
          <button className="btn-primary" onClick={() => fileRef.current?.click()}><Upload size={17} /> Importer un CV (PDF uniquement)</button>
          {cvs.length === 0 ? (
            <div className="card mt-5 p-10 text-center text-muted">Aucun CV importé. Importez-en un pour pouvoir le joindre à vos candidatures.</div>
          ) : (
            <ul className="mt-5 space-y-3">
              {cvs.map((c) => (
                <li key={c.id} className="card flex flex-wrap items-center gap-4 p-5">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{c.name} {c.main && <span className="ml-2 rounded-md bg-success-soft px-2 py-0.5 text-[11px] font-semibold text-success">Principal</span>}</p>
                    <p className="text-[12px] text-muted">Importé le {fmtDate(c.uploaded)} · {(c.size / 1024).toFixed(0)} Ko · {c.file.split('.').pop().toUpperCase()}</p>
                  </div>
                  {!c.main && <button className="btn-outline !py-2" onClick={() => mainCv(c.id)}>Définir comme principal</button>}
                  <a className="btn-outline !py-2" href={libCvUrl(c.id)}><Download size={16} /> Télécharger</a>
                  <button aria-label="Supprimer" className="rounded-lg p-2 text-red-600 hover:bg-red-50" onClick={() => confirm('Supprimer ce CV ?') && removeCv(c.id)}><Trash2 size={18} /></button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-4 text-[12px] text-muted">{tracking.filter((t) => t.fichier_cv).length} candidature(s) ont un CV joint (voir « Mes candidatures »).</p>
        </section>
      )}

      {tab !== 'mine' && (
        <Generator key={tab} mode={tab} presetCompany={params.get('company')} companies={allCompanies} meta={meta} profile={profile} completion={completion} />
      )}
    </div>
  )
}

function Generator({ mode, presetCompany, companies, meta, profile, completion }) {
  const { tracking, notify } = useStore()
  const [cid, setCid] = useState(presetCompany || '')
  const [poste, setPoste] = useState(profile.titre || '')
  const [offre, setOffre] = useState('')
  const [ton, setTon] = useState('formel')
  const [ai, setAi] = useState(!!meta.ai.enabled)
  const [tpl, setTpl] = useState('Moderne')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [cv, setCv] = useState('')
  const [mail, setMail] = useState('')
  const [letter, setLetter] = useState('')
  const [used, setUsed] = useState('')
  const company = companies.find((c) => c.id === cid)
  const track = tracking.find((t) => t.id === cid)
  const [q, setQ] = useState('')
  const list = useMemo(() => companies.filter((c) => c.short.toLowerCase().includes(q.toLowerCase())).slice(0, 80), [companies, q])

  useEffect(() => {
    if (company && !poste) setPoste(profile.titre || 'Stage PFE / Data-IT')
  }, [company, poste, profile.titre])

  const run = async () => {
    setErr('')
    if (!profile.nom) return setErr('Remplissez d’abord votre profil (nom au minimum).')
    setBusy(true)
    try {
      const body = { company_id: cid || null, entreprise: company?.short || '', poste, offre, use_ai: ai, ton }
      if (mode === 'gen') {
        const r = await api.genCv(body)
        setCv(r.cv); setMail(r.mail); setUsed(r.mode)
      } else {
        const r = await api.genLetter(body)
        setLetter(r.lettre); setUsed(r.mode)
      }
    } catch (e) {
      setErr(e.message)
    }
    setBusy(false)
  }

  const [obj, ...corps] = mail.split('\n')
  const mailto = `mailto:${track?.email || ''}?subject=${encodeURIComponent(obj.replace('Objet :', '').trim())}&body=${encodeURIComponent(corps.join('\n').trim())}`

  return (
    <div className="mt-6 grid gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
      <section className="card self-start p-5">
        {completion.percent < 40 && <p className="mb-3 rounded-lg bg-gold-soft px-3 py-2 text-[12px] text-gold-ink">Profil complété à {completion.percent}% : le CV généré sera court. Rien n’est inventé.</p>}
        <label className="block text-[13px] font-semibold">Entreprise ciblée
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrer la liste…" className={field} aria-label="Filtrer les entreprises" />
          <select value={cid} onChange={(e) => setCid(e.target.value)} className={field} aria-label="Entreprise ciblée">
            <option value="">— Aucune (générique) —</option>
            {company && !list.some((c) => c.id === cid) && <option value={cid}>{company.short}</option>}
            {list.map((c) => <option key={c.id} value={c.id}>{c.short}</option>)}
          </select>
        </label>
        <label className="mt-3 block text-[13px] font-semibold">Poste visé<input value={poste} onChange={(e) => setPoste(e.target.value)} className={field} /></label>
        {mode === 'gen' ? (
          <>
            <label className="mt-3 block text-[13px] font-semibold">Texte de l’offre (optionnel, recommandé)<textarea rows={5} value={offre} onChange={(e) => setOffre(e.target.value)} className={field} /></label>
            <div className="mt-3 flex gap-2">
              {Object.keys(TEMPLATES).map((t) => (
                <button key={t} onClick={() => setTpl(t)} aria-pressed={tpl === t} className={clsx('flex-1 rounded-lg border px-2 py-2 text-[12px]', tpl === t ? 'border-2 border-primary text-primary' : 'border-line text-muted')}>{t}</button>
              ))}
            </div>
          </>
        ) : (
          <label className="mt-3 block text-[13px] font-semibold">Ton
            <select value={ton} onChange={(e) => setTon(e.target.value)} className={field}><option value="formel">Formel</option><option value="dynamique">Dynamique</option><option value="concis">Concis</option></select>
          </label>
        )}
        <label className="mt-4 flex items-center justify-between gap-3 text-[13px]">
          <span><strong>Utiliser l’IA</strong><span className="block text-[11px] text-muted">{meta.ai.enabled ? `Fournisseur : ${meta.ai.provider}` : 'Aucune clé IA configurée : mode modèle'}</span></span>
          <input type="checkbox" checked={ai && meta.ai.enabled} disabled={!meta.ai.enabled} onChange={(e) => setAi(e.target.checked)} className="h-4 w-4 accent-primary" />
        </label>
        <button className="btn-primary mt-4 w-full" disabled={busy} onClick={run}><Sparkles size={17} />{busy ? 'Génération…' : mode === 'gen' ? 'Générer CV + e-mail' : 'Générer la lettre'}</button>
        {err && <p role="alert" className="mt-3 text-[13px] text-red-600">{err}</p>}
        <p className="mt-3 text-[11px] text-muted">Le contenu généré est un brouillon à relire : seules les informations de votre profil sont utilisées.</p>
      </section>

      <section className="space-y-5">
        {mode === 'gen' && !cv && <div className="card p-10 text-center text-muted">Le CV et l’e-mail apparaîtront ici.</div>}
        {mode === 'letter' && !letter && <div className="card p-10 text-center text-muted">La lettre apparaîtra ici.</div>}
        {mode === 'gen' && cv && (
          <>
            <div className="card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-[18px] font-medium">CV <span className="ml-2 text-[11px] font-normal text-muted">brouillon {used === 'modele' ? '(modèle)' : `(IA : ${used})`}</span></h2>
                <div className="flex gap-2">
                  <button className="btn-outline !py-2" onClick={() => download(`CV_${(company?.short || 'cv').slice(0, 20)}.md`, cv)}><Download size={16} /> .md</button>
                  <button className="btn-outline !py-2" onClick={() => printHtml('CV', cv, tpl)}><Printer size={16} /> Imprimer / PDF</button>
                </div>
              </div>
              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <textarea value={cv} onChange={(e) => setCv(e.target.value)} rows={18} aria-label="CV (modifiable)" className="w-full rounded-xl border border-line p-3 font-mono text-[12px] outline-none focus:border-primary" />
                <div className="max-h-[420px] overflow-y-auto rounded-xl border border-line bg-white p-5 text-[13px]" style={PREVIEW[tpl]} dangerouslySetInnerHTML={{ __html: mdToHtml(cv) }} />
              </div>
            </div>
            <div className="card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-[18px] font-medium">E-mail de candidature</h2>
                <a className="btn-primary !py-2" href={mailto}><Mail size={16} /> Ouvrir dans ma messagerie</a>
              </div>
              <textarea value={mail} onChange={(e) => setMail(e.target.value)} rows={9} aria-label="E-mail (modifiable)" className="mt-4 w-full rounded-xl border border-line p-3 text-[14px] outline-none focus:border-primary" />
              {!track?.email && <p className="mt-2 text-[12px] text-muted">Pas d’e-mail de contact enregistré pour cette entreprise : ajoutez-le dans « Mes candidatures ».</p>}
            </div>
          </>
        )}
        {mode === 'letter' && letter && (
          <div className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-[18px] font-medium">Lettre de motivation <span className="ml-2 text-[11px] font-normal text-muted">brouillon {used === 'modele' ? '(modèle)' : `(IA : ${used})`}</span></h2>
              <div className="flex gap-2">
                <button className="btn-outline !py-2" onClick={() => download('lettre_motivation.txt', letter)}><Download size={16} /> .txt</button>
                <button className="btn-outline !py-2" onClick={() => printHtml('Lettre', letter, 'Classique')}><Printer size={16} /> Imprimer / PDF</button>
              </div>
            </div>
            <textarea value={letter} onChange={(e) => setLetter(e.target.value)} rows={16} aria-label="Lettre (modifiable)" className="mt-4 w-full rounded-xl border border-line p-3 text-[14px] outline-none focus:border-primary" />
          </div>
        )}
      </section>
    </div>
  )
}
