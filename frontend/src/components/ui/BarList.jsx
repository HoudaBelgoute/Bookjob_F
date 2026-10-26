// Barres horizontales simples (statuts, secteurs…) sans dépendance graphique.
export default function BarList({ data, color = 'var(--primary)', suffix = '' }) {
  const entries = Object.entries(data || {})
  const max = Math.max(1, ...entries.map(([, v]) => v))
  if (!entries.length) return <p className="text-[13px] text-muted">Aucune donnée.</p>
  return (
    <ul className="space-y-2.5">
      {entries.map(([k, v]) => (
        <li key={k} className="grid grid-cols-[minmax(0,150px)_1fr_auto] items-center gap-3 text-[13px]">
          <span className="truncate text-muted" title={k}>{k}</span>
          <span className="h-2.5 rounded-full bg-chip">
            <span className="block h-full rounded-full" style={{ width: `${(v / max) * 100}%`, background: color }} />
          </span>
          <span className="w-10 text-right font-semibold">{v}{suffix}</span>
        </li>
      ))}
    </ul>
  )
}
