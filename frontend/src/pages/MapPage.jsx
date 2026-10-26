import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Crosshair, Home, MapPin } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useStore } from '../store/useStore'

const COLORS = { A: '#1f8a5b', B: '#1d5aa6', C: '#8a97aa' }
const field = 'w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] outline-none focus:border-primary'

export default function MapPage() {
  const { meta, home, setHome, clearHome, openCompany, notify } = useStore()
  const navigate = useNavigate()
  const [secteur, setSecteur] = useState('')
  const [priorite, setPriorite] = useState(['A', 'B'])
  const [dmax, setDmax] = useState('')
  const [items, setItems] = useState([])
  const [mode, setMode] = useState('adresse')
  const [adresse, setAdresse] = useState(home?.label || '')
  const [coords, setCoords] = useState({ lat: home?.lat ?? 31.6295, lon: home?.lon ?? -7.9811 })
  const [busy, setBusy] = useState(false)
  const [sel, setSel] = useState(null)
  const mapEl = useRef(null)
  const map = useRef(null)
  const layer = useRef(null)

  useEffect(() => {
    api.companies({ secteur: secteur ? [secteur] : [], priorite, dmax: dmax || undefined, sort: home ? 'distance' : 'score', limit: 500 }).then((r) => setItems(r.items))
  }, [secteur, priorite, dmax, home])

  useEffect(() => {
    if (map.current) return
    map.current = L.map(mapEl.current).setView([home?.lat ?? 31.6295, home?.lon ?? -7.9811], 12)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(map.current)
    layer.current = L.layerGroup().addTo(map.current)
    return () => {
      map.current?.remove()
      map.current = null
    }
  }, [])

  useEffect(() => {
    if (!map.current) return
    layer.current.clearLayers()
    items.forEach((c) => {
      L.circleMarker([c.lat, c.lon], { radius: sel === c.id ? 10 : 6, color: '#fff', weight: 1.5, fillColor: COLORS[c.priorite], fillOpacity: 0.9 })
        .bindTooltip(`${c.short}${c.distance_km != null ? ` · ${c.distance_km} km` : ''}`)
        .on('click', () => setSel(c.id))
        .addTo(layer.current)
    })
    if (home) L.circleMarker([home.lat, home.lon], { radius: 11, color: '#fff', weight: 2, fillColor: '#c0392b', fillOpacity: 1 }).bindTooltip('Chez vous').addTo(layer.current)
  }, [items, home, sel])

  useEffect(() => {
    if (home && map.current) map.current.setView([home.lat, home.lon], 13)
  }, [home])

  const locate = async () => {
    setBusy(true)
    try {
      const r = await api.geocode(adresse.trim())
      await setHome({ lat: r.lat, lon: r.lon, label: adresse.trim() })
    } catch (e) {
      notify(e.message)
    }
    setBusy(false)
  }
  const gps = () => {
    if (!navigator.geolocation) return notify('Géolocalisation non disponible dans ce navigateur')
    navigator.geolocation.getCurrentPosition(
      (p) => setHome({ lat: p.coords.latitude, lon: p.coords.longitude, label: 'Ma position' }),
      () => notify('Position refusée ou indisponible'),
    )
  }
  const selected = items.find((c) => c.id === sel)

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 md:px-8">
      <p className="eyebrow">Localisation</p>
      <h1 className="page-title mt-3">Carte & distance</h1>
      <p className="mt-3 max-w-3xl text-[14px] text-muted">
        Les positions sont au niveau du quartier (l’export Google Places ne contient pas de coordonnées GPS) : suffisant pour estimer un trajet, pas pour naviguer.
        {meta.google_geocoding && ' Une clé de géocodage est configurée : vous pouvez affiner les adresses depuis les Paramètres.'}
      </p>

      <div className="mt-6 grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-5">
          <section className="card p-5">
            <h2 className="flex items-center gap-2 text-[16px] font-semibold"><Home size={18} /> Ma localisation</h2>
            <div className="mt-3 inline-flex rounded-xl bg-chip p-1 text-[13px]">
              {[['adresse', 'Adresse'], ['gps', 'GPS']].map(([v, l]) => (
                <button key={v} onClick={() => setMode(v)} className={`rounded-lg px-3 py-1.5 ${mode === v ? 'bg-white font-medium shadow-card' : 'text-muted'}`}>{l}</button>
              ))}
            </div>
            {mode === 'adresse' ? (
              <form onSubmit={(e) => { e.preventDefault(); if (adresse.trim()) locate() }} className="mt-3 space-y-2">
                <input value={adresse} onChange={(e) => setAdresse(e.target.value)} placeholder="Ex. Guéliz, Marrakech" aria-label="Adresse ou quartier" className={field} />
                <button className="btn-primary w-full" disabled={busy}>{busy ? 'Recherche…' : 'Localiser'}</button>
              </form>
            ) : (
              <div className="mt-3 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <input type="number" step="0.00001" value={coords.lat} onChange={(e) => setCoords({ ...coords, lat: Number(e.target.value) })} aria-label="Latitude" className={field} />
                  <input type="number" step="0.00001" value={coords.lon} onChange={(e) => setCoords({ ...coords, lon: Number(e.target.value) })} aria-label="Longitude" className={field} />
                </div>
                <button className="btn-primary w-full" onClick={() => setHome({ ...coords, label: 'Coordonnées GPS' })}>Utiliser ces coordonnées</button>
              </div>
            )}
            <button className="btn-outline mt-2 w-full" onClick={gps}><Crosshair size={16} /> Utiliser ma position</button>
            {home && (
              <p className="mt-3 flex items-center justify-between text-[12px] text-muted">
                <span>{home.label || 'Position'} · {home.lat.toFixed(4)}, {home.lon.toFixed(4)}</span>
                <button className="text-red-600 hover:underline" onClick={clearHome}>Effacer</button>
              </p>
            )}
          </section>

          <section className="card p-5">
            <h2 className="text-[16px] font-semibold">Filtres</h2>
            <select value={secteur} onChange={(e) => setSecteur(e.target.value)} className={`${field} mt-3`} aria-label="Secteur">
              <option value="">Tous les secteurs</option>
              {meta.secteurs.map((s) => <option key={s}>{s}</option>)}
            </select>
            <div className="mt-3 flex gap-3 text-[13px]">
              {meta.priorites.map((p) => (
                <label key={p} className="flex items-center gap-1.5">
                  <input type="checkbox" className="accent-primary" checked={priorite.includes(p)} onChange={() => setPriorite(priorite.includes(p) ? priorite.filter((x) => x !== p) : [...priorite, p])} />
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[p] }} /> {p}
                </label>
              ))}
            </div>
            <label className="mt-3 block text-[13px] text-muted">
              Distance maximale (km)
              <input type="number" min="0" step="0.5" value={dmax} onChange={(e) => setDmax(e.target.value)} disabled={!home} placeholder={home ? '∞' : 'Définissez d’abord votre position'} className={`${field} mt-1`} />
            </label>
          </section>
        </aside>

        <div className="space-y-5">
          <div ref={mapEl} className="card z-0 h-[460px] overflow-hidden" role="region" aria-label="Carte des entreprises" />
          {selected && (
            <div className="card flex flex-wrap items-center gap-4 p-4">
              <MapPin className="text-primary" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{selected.short}</p>
                <p className="text-[13px] text-muted">{selected.secteur} · {selected.quartier}{selected.distance_km != null && ` · ${selected.distance_km} km`}</p>
              </div>
              <button className="btn-primary !py-2.5" onClick={() => { openCompany(selected.id); navigate('/rechercher') }}>Voir la fiche</button>
            </div>
          )}
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[14px]">
              <thead className="border-b border-line text-[12px] uppercase tracking-wider text-muted">
                <tr><th className="px-5 py-3">Entreprise</th><th className="px-5 py-3">Secteur</th><th className="px-5 py-3">Quartier</th><th className="px-5 py-3">Score</th>{home && <th className="px-5 py-3">Distance</th>}</tr>
              </thead>
              <tbody className="divide-y divide-line">
                {items.slice(0, 100).map((c) => (
                  <tr key={c.id} onClick={() => setSel(c.id)} className={`cursor-pointer hover:bg-surface ${sel === c.id ? 'bg-primary-soft/40' : ''}`}>
                    <td className="px-5 py-3 font-medium">{c.short}</td><td className="px-5 py-3 text-muted">{c.secteur}</td><td className="px-5 py-3 text-muted">{c.quartier}</td><td className="px-5 py-3">{c.score}</td>
                    {home && <td className="px-5 py-3">{c.distance_km} km</td>}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-5 py-3 text-[12px] text-muted">{items.length} entreprises{items.length > 100 ? ' (100 premières affichées)' : ''}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
