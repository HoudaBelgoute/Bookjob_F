import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { fmtDate } from '../data/data'

const PALETTE = ['#7C5CFC', '#20C7B7', '#FFB454', '#F56B8A', '#5DA9FF', '#A3E635']
const STATUS_COLORS = {
  'Candidature envoyée': '#7C5CFC',
  'En cours de traitement': '#20C7B7',
  'Entretien programmé': '#FFB454',
  Acceptée: '#A3E635',
  Refusée: '#F56B8A',
  Brouillon: '#94A3B8',
  'À envoyer': '#5DA9FF',
}

function Panel({ title, eyebrow, subtitle, children, className = '' }) {
  return (
    <section className={`chart-panel ${className}`}>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          {eyebrow && <p className="chart-eyebrow">{eyebrow}</p>}
          <h2 className="text-[17px] font-semibold tracking-tight text-slate-900">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

function MetricCard({ label, value, detail, icon, index = 0 }) {
  return (
    <article className="metric-card" style={{ animationDelay: `${index * 90}ms` }}>
      <div className="flex items-start justify-between gap-3">
        <span className="metric-icon" aria-hidden="true">{icon}</span>
        <span className="metric-spark" aria-hidden="true">↗</span>
      </div>
      <p className="mt-5 text-[13px] font-medium text-slate-500">{label}</p>
      <div className="mt-1 text-3xl font-bold tracking-tight text-slate-900 tabular-nums">{value ?? '—'}</div>
      {detail && <p className="mt-2 text-xs text-slate-500">{detail}</p>}
    </article>
  )
}

function AnimatedDonut({ items, total }) {
  const safeItems = items.filter((item) => item.value > 0)
  const sum = safeItems.reduce((acc, item) => acc + item.value, 0)
  const circumference = 2 * Math.PI * 67
  let offset = 0
  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
      <div className="relative h-[190px] w-[190px] shrink-0">
        <svg viewBox="0 0 180 180" className="h-full w-full -rotate-90 overflow-visible" role="img" aria-label="Répartition des candidatures par statut">
          <circle cx="90" cy="90" r="67" fill="none" stroke="#EEF0F8" strokeWidth="18" />
          {safeItems.map((item, index) => {
            const length = sum ? (item.value / sum) * circumference : 0
            const currentOffset = offset
            offset += length
            return (
              <circle
                key={item.label}
                className="donut-segment"
                cx="90" cy="90" r="67" fill="none"
                stroke={STATUS_COLORS[item.label] || PALETTE[index % PALETTE.length]}
                strokeWidth="18"
                strokeLinecap="round"
                strokeDasharray={`${length} ${circumference - length}`}
                strokeDashoffset={-currentOffset}
                style={{ animationDelay: `${index * 120}ms` }}
              />
            )
          })}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold tracking-tight text-slate-900">{total}</span>
          <span className="mt-1 text-[11px] font-semibold uppercase tracking-[.16em] text-slate-400">candidatures</span>
        </div>
      </div>
      <div className="grid w-full gap-3">
        {safeItems.length ? safeItems.map((item, index) => (
          <div key={item.label} className="flex items-center gap-3">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: STATUS_COLORS[item.label] || PALETTE[index % PALETTE.length] }} />
            <span className="min-w-0 flex-1 truncate text-sm text-slate-600">{item.label}</span>
            <strong className="text-sm text-slate-900">{item.value}</strong>
            <span className="w-10 text-right text-xs text-slate-400">{sum ? Math.round(item.value / sum * 100) : 0}%</span>
          </div>
        )) : <p className="text-sm text-slate-500">Pas encore de candidatures sur cette période.</p>}
      </div>
    </div>
  )
}

function WeeklyArea({ items }) {
  const points = useMemo(() => {
    if (!items.length) return []
    const max = Math.max(1, ...items.map((item) => item.count))
    const width = 620
    const height = 220
    const left = 28
    const right = 12
    const top = 16
    const bottom = 30
    const innerW = width - left - right
    const innerH = height - top - bottom
    return items.map((item, index) => ({
      ...item,
      x: left + (items.length === 1 ? innerW / 2 : index * innerW / (items.length - 1)),
      y: top + innerH - (item.count / max) * innerH,
      max,
      height,
    }))
  }, [items])
  if (!items.length) return <p className="py-10 text-center text-sm text-slate-500">Aucune candidature datée sur cette période.</p>
  const line = points.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ')
  const area = `${line} L ${points[points.length - 1].x} 190 L ${points[0].x} 190 Z`
  const max = Math.max(1, ...items.map((item) => item.count))
  return (
    <div className="w-full">
      <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
        <span>Volume par semaine</span><span>Pic : {max}</span>
      </div>
      <svg viewBox="0 0 620 220" className="w-full overflow-visible" role="img" aria-label="Évolution hebdomadaire des candidatures">
        <defs>
          <linearGradient id="weeklyGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#7C5CFC" stopOpacity=".28" />
            <stop offset="100%" stopColor="#7C5CFC" stopOpacity=".015" />
          </linearGradient>
          <filter id="softGlow"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        {[0, 1, 2, 3].map((n) => <line key={n} x1="28" x2="608" y1={16 + n * 58} y2={16 + n * 58} stroke="#E9EAF3" strokeDasharray="4 6" />)}
        <path d={area} fill="url(#weeklyGradient)" className="area-in" />
        <path d={line} fill="none" stroke="#7C5CFC" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" className="line-in" filter="url(#softGlow)" />
        {points.map((p) => (
          <g key={p.week} className="point-in">
            <circle cx={p.x} cy={p.y} r="7" fill="#fff" stroke="#7C5CFC" strokeWidth="3" />
            <title>{fmtDate(p.week)} : {p.count} candidature(s)</title>
            <text x={p.x} y={Math.max(12, p.y - 13)} fontSize="10" fontWeight="700" fill="#5B43C7" textAnchor="middle">{p.count}</text>
          </g>
        ))}
        {points.filter((_, i) => points.length <= 8 || i % Math.ceil(points.length / 8) === 0 || i === points.length - 1).map((p) => (
          <text key={`label-${p.week}`} x={p.x} y="211" fontSize="10" fill="#94A3B8" textAnchor="middle">{fmtDate(p.week)}</text>
        ))}
      </svg>
    </div>
  )
}

function HorizontalBars({ items, color = '#20C7B7', suffix = '' }) {
  const max = Math.max(1, ...items.map((item) => Number(item.value) || 0))
  if (!items.length) return <p className="py-8 text-sm text-slate-500">Aucune donnée disponible.</p>
  return (
    <div className="space-y-4">
      {items.map((item, index) => (
        <div key={item.label} className="bar-row" style={{ animationDelay: `${index * 70}ms` }}>
          <div className="mb-1.5 flex items-center justify-between gap-3">
            <span className="truncate text-sm text-slate-600">{item.label}</span>
            <strong className="shrink-0 text-sm text-slate-900">{item.value}{suffix}</strong>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
            <div className="animated-bar h-full rounded-full" style={{ width: `${Math.max(1, (Number(item.value) / max) * 100)}%`, background: color, animationDelay: `${index * 70}ms` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function PriorityOrbit({ priorities = {} }) {
  const items = Object.entries(priorities).sort(([a], [b]) => a.localeCompare(b))
  const total = items.reduce((sum, [, value]) => sum + Number(value || 0), 0)
  return (
    <div className="grid grid-cols-3 gap-3">
      {items.map(([label, value], index) => {
        const pct = total ? Math.round(value / total * 100) : 0
        return (
          <div key={label} className="priority-tile" style={{ animationDelay: `${index * 100}ms` }}>
            <div className="relative mx-auto flex h-20 w-20 items-center justify-center rounded-full" style={{ background: `conic-gradient(${PALETTE[index % PALETTE.length]} ${pct}%, #EEF0F8 ${pct}% 100%)` }}>
              <div className="flex h-[62px] w-[62px] flex-col items-center justify-center rounded-full bg-white">
                <strong className="text-lg text-slate-900">{value}</strong>
                <span className="text-[10px] text-slate-400">{pct}%</span>
              </div>
            </div>
            <p className="mt-3 text-center text-xs font-semibold text-slate-600">Priorité {label}</p>
          </div>
        )
      })}
      {!items.length && <p className="col-span-3 text-sm text-slate-500">Aucune donnée de priorité.</p>}
    </div>
  )
}

function DataQuality({ q, error }) {
  if (error) return <p role="alert" className="mt-8 text-sm text-red-600">Qualité des données : {error}</p>
  if (!q) return <p className="mt-8 text-sm text-slate-400">Chargement des indicateurs de qualité…</p>
  const figures = [
    ['Base nettoyée', q.rows_clean ?? '—', '◈'],
    ['Lignes exclues', q.rows_excluded ?? '—', '⌁'],
    ['Coordonnées exactes', q.exact_coordinates ?? '—', '⌖'],
    ['Doublons restants', q.duplicate_ids ?? '—', '⟲'],
  ]
  return (
    <section className="mt-10">
      <div className="mb-4">
        <p className="chart-eyebrow">DATA LAB</p>
        <h2 className="text-xl font-bold tracking-tight text-slate-900">Qualité des données</h2>
        <p className="mt-1 text-sm text-slate-500">Contrôle de la base entreprises et de son nettoyage.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {figures.map(([label, value, icon], index) => <MetricCard key={label} label={label} value={value} icon={icon} index={index} />)}
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Panel title="Complétude des champs" eyebrow="COUVERTURE" subtitle="Pourcentage de lignes renseignées">
          <HorizontalBars items={(q.completeness || []).map((item) => ({ label: item.field, value: item.percent }))} color="#7C5CFC" suffix="%" />
        </Panel>
        <Panel title="Répartition des priorités" eyebrow="SCORING" subtitle="Entreprises classées par niveau">
          <PriorityOrbit priorities={q.priorities} />
        </Panel>
      </div>
      {!!q.report?.length && (
        <Panel title="Nettoyage et anomalies" eyebrow="JOURNAL" className="mt-5">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-slate-400"><tr><th className="pb-3 pr-4">Problème</th><th className="pb-3 pr-4">Lignes</th><th className="pb-3">Traitement appliqué</th></tr></thead>
              <tbody>{q.report.map((row, index) => <tr key={`${row.probleme}-${index}`} className="border-t border-slate-100 align-top"><td className="py-3 pr-4 font-medium text-slate-700">{row.probleme}</td><td className="py-3 pr-4 font-semibold text-slate-900">{row.lignes}</td><td className="py-3 text-slate-500">{row.traitement}</td></tr>)}</tbody>
            </table>
          </div>
        </Panel>
      )}
    </section>
  )
}

export default function Statistics() {
  const [period, setPeriod] = useState({ start: '', end: '' })
  const [data, setData] = useState(null)
  const [quality, setQuality] = useState(null)
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState('')
  const [qualityError, setQualityError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    setBusy(true)
    setError('')
    try {
      setData(await api.stats(period.start, period.end))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    load()
    api.dataQuality().then(setQuality).catch((e) => setQualityError(e.message))
    api.meta().then(setMeta).catch(() => {})
  }, [])

  const statusItems = Object.entries(data?.by_status || {}).map(([label, value]) => ({ label, value }))
  const kpis = data ? [
    ['Candidatures suivies', data.kpis.total, '✳', 'Sur la période sélectionnée'],
    ['Réponses reçues', data.kpis.responses, '↗', `${data.kpis.response_rate}% de réponse`],
    ['Entretiens', data.kpis.interviews, '◎', 'Étapes vers le recrutement'],
    ['Acceptations', data.kpis.acceptances, '✦', `${data.kpis.acceptance_rate}% d’acceptation`],
  ] : []
  const sectors = Object.entries(meta?.secteur_counts || {}).sort((a, b) => b[1] - a[1]).slice(0, 7).map(([label, value]) => ({ label, value }))
  const positives = data ? [
    { label: 'Entretiens', value: data.kpis.interviews },
    { label: 'Acceptations', value: data.kpis.acceptances },
    { label: 'Refus', value: data.kpis.refusals },
  ] : []

  return (
    <div className="stats-experience mx-auto max-w-[1500px] px-4 py-8 md:px-8">
      <style>{`
        .stats-experience { --chart-ink:#17213d; color:#17213d; }
        .chart-panel { min-width:0; padding:24px; border:1px solid rgba(225,228,241,.9); border-radius:22px; background:rgba(255,255,255,.92); box-shadow:0 12px 34px rgba(31,41,85,.045); transition:transform .25s ease, box-shadow .25s ease; }
        .chart-panel:hover { transform:translateY(-2px); box-shadow:0 18px 38px rgba(31,41,85,.08); }
        .chart-eyebrow { margin-bottom:7px; color:#8a7be8; font-size:10px; font-weight:800; letter-spacing:.18em; }
        .metric-card { min-width:0; padding:19px; border:1px solid #e7e9f4; border-radius:20px; background:linear-gradient(145deg,#fff 0%,#f8f9ff 100%); box-shadow:0 8px 24px rgba(31,41,85,.04); animation:rise-in .55s both; transition:transform .25s ease,border-color .25s ease; }
        .metric-card:hover { transform:translateY(-4px); border-color:#c8c0ff; }
        .metric-icon { display:grid; width:39px; height:39px; place-items:center; border-radius:13px; background:#f0edff; color:#7255f6; font-size:20px; }
        .metric-spark { display:grid; width:25px; height:25px; place-items:center; border-radius:50%; background:#e8faf5; color:#0d9e85; font-size:14px; }
        .animated-bar { transform-origin:left; animation:bar-grow .9s cubic-bezier(.2,.8,.2,1) both; }
        .bar-row { animation:fade-in .5s both; }
        .donut-segment { animation:donut-in .9s cubic-bezier(.2,.8,.2,1) both; }
        .line-in { stroke-dasharray:1200; stroke-dashoffset:1200; animation:draw-line 1.5s ease forwards; }
        .area-in { opacity:0; animation:fade-in .8s .25s forwards; }
        .point-in { opacity:0; animation:fade-in .35s .7s forwards; }
        .priority-tile { animation:rise-in .6s both; transition:transform .25s ease; }
        .priority-tile:hover { transform:scale(1.04); }
        @keyframes rise-in { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
        @keyframes fade-in { to { opacity:1; } }
        @keyframes bar-grow { from { transform:scaleX(0); } to { transform:scaleX(1); } }
        @keyframes draw-line { to { stroke-dashoffset:0; } }
        @keyframes donut-in { from { stroke-dasharray:0 500; } }
        @media (prefers-reduced-motion: reduce) { .stats-experience *, .stats-experience *::before, .stats-experience *::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; transition-duration:.01ms !important; } }
        @media (max-width:640px) { .chart-panel { padding:17px; border-radius:18px; } .metric-card { padding:15px; } }
      `}</style>

      <div className="relative mb-7 overflow-hidden rounded-[28px] bg-slate-950 px-6 py-7 text-white md:px-9 md:py-9">
        <div className="pointer-events-none absolute -right-10 -top-24 h-72 w-72 rounded-full bg-violet-500/30 blur-3xl" />
        <div className="pointer-events-none absolute right-36 top-20 h-40 w-40 rounded-full bg-teal-400/20 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <p className="text-[10px] font-extrabold uppercase tracking-[.24em] text-violet-300">BOOKJOB · ANALYTICS STUDIO</p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight md:text-4xl">Tes données, en mouvement.</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300">Un tableau de bord vivant pour comprendre ton rythme, suivre tes résultats et repérer les tendances.</p>
          </div>
          <div className="flex flex-wrap items-end gap-2 rounded-2xl border border-white/10 bg-white/5 p-3 backdrop-blur">
            <label className="text-xs text-slate-300">Du<input type="date" value={period.start} onChange={(event) => setPeriod({ ...period, start: event.target.value })} className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white" /></label>
            <label className="text-xs text-slate-300">Au<input type="date" value={period.end} onChange={(event) => setPeriod({ ...period, end: event.target.value })} className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white" /></label>
            <button disabled={busy} onClick={load} className="rounded-lg bg-violet-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-400 disabled:opacity-60">{busy ? 'Analyse…' : 'Actualiser ↗'}</button>
          </div>
        </div>
        {data?.period && <p className="relative mt-5 text-xs text-slate-400">Période analysée : {fmtDate(data.period.start)} — {fmtDate(data.period.end)} · Les statistiques sont calculées à partir des candidatures datées.</p>}
      </div>

      {error && <p role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</p>}
      {!data && !error && <p className="py-8 text-sm text-slate-500">Chargement de ton espace analytique…</p>}

      {data && <>
        <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {kpis.map(([label, value, icon, detail], index) => <MetricCard key={label} label={label} value={value} icon={icon} detail={detail} index={index} />)}
        </div>
        <div className="grid gap-5 xl:grid-cols-[1.45fr_1fr]">
          <Panel title="Le rythme de tes candidatures" eyebrow="ACTIVITÉ · TIMELINE" subtitle="Une courbe animée pour repérer les accélérations et les périodes calmes.">
            <WeeklyArea items={data.weekly || []} />
          </Panel>
          <Panel title="Ton pipeline" eyebrow="RÉPARTITION · STATUTS" subtitle="La part de chaque étape dans la période sélectionnée.">
            <AnimatedDonut items={statusItems} total={data.kpis.total} />
          </Panel>
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <Panel title="Les entreprises qui reviennent le plus" eyebrow="TOP ENTREPRISES" subtitle="Classement des entreprises associées à tes candidatures.">
            <HorizontalBars items={(data.top_companies || []).map((item) => ({ label: item.company, value: item.count }))} color="#7C5CFC" />
          </Panel>
          <Panel title="L'issue des candidatures" eyebrow="RÉSULTATS" subtitle="Vue comparative des résultats enregistrés.">
            <HorizontalBars items={positives} color="#20C7B7" />
            <div className="mt-5 rounded-xl bg-violet-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-violet-500">Taux de réponse</p>
              <div className="mt-1 flex items-baseline gap-2"><strong className="text-3xl text-slate-900">{data.kpis.response_rate}%</strong><span className="text-xs text-slate-500">des candidatures de la période</span></div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-white"><div className="animated-bar h-full rounded-full bg-violet-500" style={{ width: `${Math.min(100, Math.max(0, data.kpis.response_rate))}%` }} /></div>
            </div>
          </Panel>
        </div>
      </>}

      <div className="mt-10 mb-4">
        <p className="chart-eyebrow">ENTREPRISES · DATA EXPLORER</p>
        <h2 className="text-xl font-bold tracking-tight text-slate-900">Panorama de la base entreprises</h2>
        <p className="mt-1 text-sm text-slate-500">Indicateurs calculés à partir de la base nettoyée connectée au backend.</p>
      </div>
      {meta && <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
        <MetricCard label="Entreprises dans la base" value={meta.total_entreprises} icon="◈" index={0} />
        <MetricCard label="Secteurs identifiés" value={Object.keys(meta.secteur_counts || {}).length} icon="⌘" index={1} />
        <MetricCard label="Favoris et suivi" value="En direct" detail="Consulte les fiches entreprises" icon="◎" index={2} />
        <MetricCard label="Données" value="Nettoyées" detail="Statistiques issues du backend" icon="✦" index={3} />
      </div>}
      {meta && <Panel title="Carte des secteurs" eyebrow="MARCHÉ · SECTEURS" subtitle="Comparaison des volumes dans les catégories de la base.">
        <HorizontalBars items={sectors} color="#FFB454" />
      </Panel>}

      <DataQuality q={quality} error={qualityError} />
    </div>
  )
}
