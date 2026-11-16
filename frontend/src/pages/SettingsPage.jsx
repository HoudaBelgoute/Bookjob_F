import { useEffect, useState } from 'react'
import { api, exportUrl } from '../api'
import { useAuth } from '../components/AuthGate'
import { useStore } from '../store/useStore'

function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 py-4">
      <span><span className="block text-[14px] font-semibold">{label}</span><span className="block text-[12px] text-muted">{hint}</span></span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span className="relative h-6 w-11 shrink-0 rounded-full bg-[#c5cedc] transition-colors peer-checked:bg-primary peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-primary after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-transform peer-checked:after:translate-x-5" />
    </label>
  )
}

const API_PROVIDERS = [
  { id: 'groq', label: 'Groq', category: 'ai', field: 'Clé API Groq', placeholder: 'Clé API Groq personnelle' },
  { id: 'anthropic', label: 'Anthropic / Claude', category: 'ai', field: 'Clé API Anthropic', placeholder: 'Clé API Anthropic personnelle' },
  { id: 'google_places', label: 'Google Places', category: 'data', field: 'Clé Google Places API', placeholder: 'Clé Google Places API personnelle' },
  { id: 'jooble', label: 'Jooble', category: 'data', field: 'Clé API Jooble', placeholder: 'Clé API Jooble personnelle' },
]

function ProviderKeyCard({ provider, status, value, error, busy, onChange, onSave, onDelete }) {
  const configured = status?.personal_key_configured
  const statusText = !status ? 'Chargement du statut…' :
    configured && !status.personal_key_usable ? 'Clé personnelle indisponible : vérifie la configuration de chiffrement.' :
      configured ? `Clé personnelle enregistrée (${status.masked_key}), prioritaire sur la clé serveur.` :
        status.server_key_configured ? 'Aucune clé personnelle : la clé serveur sera utilisée.' : 'Aucune clé configurée.'

  return (
    <div className="space-y-3 rounded-xl border border-line p-4">
      <div>
        <h3 className="text-[14px] font-semibold">{provider.label}</h3>
        <p className="mt-1 text-[12px] text-muted">{statusText}</p>
      </div>
      <form onSubmit={onSave} className="space-y-2">
        <label htmlFor={`key-${provider.id}`} className="block text-[12px] font-semibold">{provider.field}</label>
        <div className="flex flex-wrap gap-2">
          <input
            id={`key-${provider.id}`}
            type="password"
            autoComplete="new-password"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={configured ? 'Remplacer la clé enregistrée' : provider.placeholder}
            className="min-w-[220px] flex-1 rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] outline-none focus:border-primary"
          />
          <button type="submit" className="btn-primary" disabled={busy || !value.trim() || !status?.encryption_available}>
            {busy ? 'Vérification…' : 'Tester et enregistrer'}
          </button>
        </div>
        {!status?.encryption_available && status && (
          <p className="text-[12px] text-muted">Le serveur doit configurer BOOKJOB_API_KEY_ENCRYPTION_KEY (ou l’ancien nom BOOKJOB_AI_KEY_ENCRYPTION_KEY). Aucune clé ne sera stockée sans chiffrement.</p>
        )}
        {error && <p role="alert" className="text-[12px] text-red-700">{error}</p>}
      </form>
      {configured && (
        <button type="button" className="text-[12px] font-semibold text-red-600 underline" disabled={busy} onClick={onDelete}>
          Supprimer ma clé personnelle
        </button>
      )}
    </div>
  )
}

export default function SettingsPage() {
  const { settings, setSetting, alerts, removeAlert, meta, home, clearHome, notify, refreshTracking, refreshCompanies } = useStore()
  const { signOut: authSignOut } = useAuth()
  const [busy, setBusy] = useState(false)
  const [gmailConnected, setGmailConnected] = useState(Boolean(meta?.email?.connected))
  const [keyStatuses, setKeyStatuses] = useState({})
  const [keyInputs, setKeyInputs] = useState({})
  const [keyErrors, setKeyErrors] = useState({})
  const [keyBusy, setKeyBusy] = useState('')
  const [sourceProvider, setSourceProvider] = useState('google_places')
  const [sourceQuery, setSourceQuery] = useState('')
  const [sourceLocation, setSourceLocation] = useState('')
  const [sourcePreview, setSourcePreview] = useState(null)
  const [selectedSourceItems, setSelectedSourceItems] = useState([])
  const [savedPlaceIds, setSavedPlaceIds] = useState([])
  const [refreshedPlaces, setRefreshedPlaces] = useState([])
  const [sourceBusy, setSourceBusy] = useState(false)
  const [sourceError, setSourceError] = useState('')

  useEffect(() => {
    setGmailConnected(Boolean(meta?.email?.connected))
  }, [meta?.email?.connected])

  useEffect(() => {
    api.integrationKeyStatuses()
      .then(({ items }) => setKeyStatuses(Object.fromEntries(items.map((item) => [item.provider, item]))))
      .catch((error) => setSourceError(error.message || 'Impossible de charger le statut des intégrations.'))
    api.savedGooglePlaces()
      .then(({ place_ids }) => setSavedPlaceIds(place_ids))
      .catch((error) => setSourceError(error.message || 'Impossible de charger les lieux enregistrés.'))
  }, [])

  const saveKey = (provider) => async (event) => {
    event.preventDefault()
    setKeyBusy(provider.id)
    setKeyErrors((current) => ({ ...current, [provider.id]: '' }))
    try {
      const status = await api.saveIntegrationKey(provider.id, keyInputs[provider.id] || '')
      setKeyStatuses((current) => ({ ...current, [provider.id]: status }))
      setKeyInputs((current) => ({ ...current, [provider.id]: '' }))
      notify(`Clé ${provider.label} vérifiée et enregistrée de façon chiffrée`)
    } catch (error) {
      setKeyErrors((current) => ({ ...current, [provider.id]: error.message || 'Impossible de vérifier cette clé.' }))
    } finally {
      setKeyBusy('')
    }
  }

  const removeKey = (provider) => async () => {
    setKeyBusy(provider.id)
    try {
      const status = await api.deleteIntegrationKey(provider.id)
      setKeyStatuses((current) => ({ ...current, [provider.id]: status }))
      notify(`Clé personnelle ${provider.label} supprimée`)
    } catch (error) {
      setKeyErrors((current) => ({ ...current, [provider.id]: error.message || 'Impossible de supprimer cette clé.' }))
    } finally {
      setKeyBusy('')
    }
  }

  const searchSource = async (event) => {
    event.preventDefault()
    setSourceBusy(true)
    setSourceError('')
    try {
      const result = await api.searchDataSource(sourceProvider, sourceQuery, sourceLocation)
      setSourcePreview(result)
      setSelectedSourceItems(result.items.map((item) => item.id))
      if (!result.items.length) notify('Aucun résultat trouvé')
    } catch (error) {
      setSourceError(error.message || 'La recherche a échoué.')
    } finally {
      setSourceBusy(false)
    }
  }

  const importSourceItems = async () => {
    if (!sourcePreview || !selectedSourceItems.length) return
    setSourceBusy(true)
    setSourceError('')
    try {
      const selectedItems = sourcePreview.items.filter((item) => selectedSourceItems.includes(item.id))
      const ids = sourceProvider === 'google_places'
        ? selectedItems.map((item) => item.external_id).filter(Boolean)
        : selectedSourceItems
      const result = await api.importDataSourceResults(sourceProvider, sourcePreview.review_id, ids)
      if (sourceProvider === 'google_places') setSavedPlaceIds(result.saved_place_ids)
      else await refreshTracking()
      setSourcePreview(null)
      setSelectedSourceItems([])
      notify(sourceProvider === 'google_places'
        ? `${result.added_count} nouveau${result.added_count > 1 ? 'x' : ''} lieu${result.added_count > 1 ? 'x' : ''} Google Places enregistré${result.added_count > 1 ? 's' : ''}; les détails ne sont pas copiés`
        : `${result.imported.length} offre(s) ajoutée(s) au suivi${result.duplicates ? `, ${result.duplicates} doublon(s) ignoré(s)` : ''}`)
    } catch (error) {
      setSourceError(error.message || 'Impossible d’importer ces résultats.')
    } finally {
      setSourceBusy(false)
    }
  }

  const refreshSavedPlaces = async () => {
    setSourceBusy(true)
    setSourceError('')
    try {
      const result = await api.refreshGooglePlaces()
      setRefreshedPlaces(result.items)
    } catch (error) {
      setSourceError(error.message || 'Impossible d’actualiser les lieux Google Places.')
    } finally {
      setSourceBusy(false)
    }
  }

  const removeSavedPlace = async (placeId) => {
    try {
      const result = await api.deleteGooglePlace(placeId)
      setSavedPlaceIds(result.place_ids)
      setRefreshedPlaces((current) => current.filter((place) => place.external_id !== placeId))
    } catch (error) {
      setSourceError(error.message || 'Impossible de supprimer ce lieu.')
    }
  }

  const refine = async () => {
    setBusy(true)
    try {
      const r = await api.geocodeCompanies()
      await refreshCompanies()
      notify(`${r.geocoded} adresses géocodées (${r.failed} échecs)`)
    } catch (e) {
      notify(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }
  const reset = async () => {
    if (!confirm('Supprimer TOUT le suivi et les CV joints ? Action irréversible.')) return
    setBusy(true)
    try {
      await api.resetTracking()
      await refreshTracking()
      notify('Suivi réinitialisé')
    } catch (e) {
      notify(e.message || 'Impossible de réinitialiser le suivi.', 'error')
    } finally {
      setBusy(false)
    }
  }
  const signOutAll = async () => {
    if (!confirm('Se déconnecter de BookJob ? Tes données et ton compte Gmail resteront associés à ton compte.')) return
    setBusy(true)
    try {
      await authSignOut()
    } catch (e) {
      notify(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-[800px] px-4 py-8 md:px-8">
      <p className="eyebrow">Compte</p>
      <h1 className="page-title mt-3">Paramètres</h1>

      <section className="card mt-8 divide-y divide-line px-6">
        <Toggle checked={!!settings.useProfileForAI} onChange={(v) => setSetting({ useProfileForAI: v })} label="Autoriser l’IA à utiliser mon profil" hint="Désactivé : l’assistant ne reçoit aucune donnée personnelle." />
        <div className="space-y-4 py-5">
          <div>
            <h2 className="text-[16px] font-semibold">IA</h2>
            <p className="mt-1 text-[12px] text-muted">Groq et Anthropic/Claude sont branchés au CV Studio, aux lettres et à l’assistant.</p>
          </div>
          <label className="block text-[12px] font-semibold" htmlFor="ai-provider">Fournisseur IA utilisé</label>
          <select id="ai-provider" value={settings.aiProvider || 'auto'} onChange={(event) => setSetting({ aiProvider: event.target.value })} className="rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px]">
            <option value="auto">Automatique : clé personnelle, puis clé serveur</option>
            <option value="groq">Groq</option>
            <option value="anthropic">Anthropic / Claude</option>
          </select>
          <div className="grid gap-3 md:grid-cols-2">
            {API_PROVIDERS.filter((provider) => provider.category === 'ai').map((provider) => (
              <ProviderKeyCard
                key={provider.id}
                provider={provider}
                status={keyStatuses[provider.id]}
                value={keyInputs[provider.id] || ''}
                error={keyErrors[provider.id]}
                busy={keyBusy === provider.id}
                onChange={(value) => setKeyInputs((current) => ({ ...current, [provider.id]: value }))}
                onSave={saveKey(provider)}
                onDelete={removeKey(provider)}
              />
            ))}
          </div>
          <p className="text-[12px] text-muted">Les clés sont envoyées uniquement au backend, testées auprès du fournisseur et chiffrées au repos. Sans clé utilisateur, la clé serveur correspondante est utilisée; sans aucune clé IA, BookJob conserve son mode local.</p>
        </div>
        <div className="space-y-4 py-5">
          <div>
            <h2 className="text-[16px] font-semibold">Sources de données</h2>
            <p className="mt-1 text-[12px] text-muted">Recherche à la demande : Google Places pour les entreprises et Jooble, distinctement, pour les annonces.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {API_PROVIDERS.filter((provider) => provider.category === 'data').map((provider) => (
              <ProviderKeyCard
                key={provider.id}
                provider={provider}
                status={keyStatuses[provider.id]}
                value={keyInputs[provider.id] || ''}
                error={keyErrors[provider.id]}
                busy={keyBusy === provider.id}
                onChange={(value) => setKeyInputs((current) => ({ ...current, [provider.id]: value }))}
                onSave={saveKey(provider)}
                onDelete={removeKey(provider)}
              />
            ))}
          </div>
          <form onSubmit={searchSource} className="space-y-3 rounded-xl bg-surface p-4">
            <label htmlFor="data-provider" className="block text-[12px] font-semibold">Source de la recherche</label>
            <select id="data-provider" value={sourceProvider} onChange={(event) => { setSourceProvider(event.target.value); setSourcePreview(null) }} className="rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px]">
              <option value="google_places">Google Places — entreprises / lieux</option>
              <option value="jooble">Jooble — offres d’emploi</option>
            </select>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-[12px] font-semibold">
                {sourceProvider === 'jooble' ? 'Mots-clés' : 'Recherche d’entreprise / activité'}
                <input required maxLength={150} value={sourceQuery} onChange={(event) => setSourceQuery(event.target.value)} placeholder={sourceProvider === 'jooble' ? 'Ex. stage data' : 'Ex. cabinet comptable'} className="mt-1 w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] font-normal" />
              </label>
              <label className="block text-[12px] font-semibold">
                Localisation
                <input maxLength={100} value={sourceLocation} onChange={(event) => setSourceLocation(event.target.value)} placeholder="Ex. Marrakech" className="mt-1 w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] font-normal" />
              </label>
            </div>
            <button type="submit" className="btn-outline" disabled={sourceBusy || !sourceQuery.trim()}>{sourceBusy ? 'Recherche…' : 'Rechercher des résultats'}</button>
            <p className="text-[12px] text-muted">Les résultats apparaissent d’abord en aperçu. Les offres Jooble sélectionnées sont ajoutées au suivi avec source et date de récupération; les doublons sont ignorés. Pour respecter les règles Google Maps, BookJob ne conserve que l’identifiant Place des lieux choisis, pas leur nom, adresse ou autres contenus.</p>
          </form>
          {sourceError && <p role="alert" className="text-[13px] text-red-700">{sourceError}</p>}
          {sourcePreview && (
            <div className="space-y-3">
              {sourcePreview.items.length ? sourcePreview.items.map((item) => (
                <label key={item.id} className="flex items-start gap-3 rounded-xl border border-line p-3 text-[13px]">
                  <input type="checkbox" checked={selectedSourceItems.includes(item.id)} onChange={(event) => setSelectedSourceItems((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} className="mt-1 accent-primary" />
                  <span className="min-w-0 flex-1">
                    <strong className="block">{item.title}</strong>
                    <span className="block text-muted">{item.company && item.company !== item.title ? `${item.company} · ` : ''}{item.location}</span>
                    {item.description && <span className="mt-1 block text-muted">{item.description}</span>}
                    {item.url && <span className="mt-1 block truncate text-primary">{item.url}</span>}
                  </span>
                </label>
              )) : <p className="text-[13px] text-muted">Aucun résultat dans cette recherche.</p>}
              {!!selectedSourceItems.length && <button type="button" className="btn-primary" onClick={importSourceItems} disabled={sourceBusy}>{sourcePreview.provider === 'google_places' ? `Enregistrer ${selectedSourceItems.length} identifiant(s) Place` : `Ajouter ${selectedSourceItems.length} offre(s) à mon suivi`}</button>}
              {sourcePreview.provider === 'google_places' && <p className="text-[11px] text-muted">Aperçu temporaire attribué à Google Maps. BookJob conserve seulement les identifiants Place exemptés des restrictions de stockage; les détails sont redemandés à Google lorsqu’on les actualise.</p>}
            </div>
          )}
          {savedPlaceIds.length > 0 && (
            <div className="space-y-3 rounded-xl border border-line p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-[14px] font-semibold">Mes lieux Google Places enregistrés ({savedPlaceIds.length})</h3>
                <button type="button" className="btn-outline" disabled={sourceBusy} onClick={refreshSavedPlaces}>Actualiser les détails depuis Google</button>
              </div>
              <p className="text-[12px] text-muted">Seuls les Place ID sont enregistrés durablement; les détails affichés ci-dessous proviennent d’un nouvel appel Google.</p>
              {refreshedPlaces.map((place) => (
                <div key={place.external_id} className="flex items-start justify-between gap-3 border-t border-line pt-3 text-[13px]">
                  <span className="min-w-0">
                    <strong className="block">{place.title}</strong>
                    <span className="block text-muted">{place.sector}{place.location ? ` · ${place.location}` : ''}</span>
                    {place.url && <a className="block truncate text-primary hover:underline" href={place.url} target="_blank" rel="noreferrer">Ouvrir dans Google Maps</a>}
                  </span>
                  <button type="button" className="shrink-0 text-[12px] text-red-600 underline" onClick={() => removeSavedPlace(place.external_id)}>Retirer</button>
                </div>
              ))}
              {savedPlaceIds.map((id) => !refreshedPlaces.some((place) => place.external_id === id) && (
                <div key={id} className="flex items-center justify-between gap-3 border-t border-line pt-2 text-[12px] text-muted">
                  <code className="truncate">{id}</code>
                  <button type="button" className="text-red-600 underline" onClick={() => removeSavedPlace(id)}>Retirer</button>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="py-4">
          <button type="button" className="btn-outline" onClick={() => setSetting({ onboardingCompleted: false })}>
            Revoir le guide de démarrage
          </button>
        </div>
      </section>

      <section className="card mt-5 p-6">
        <h2 className="text-[18px] font-medium">Recherches enregistrées</h2>
        {alerts.length === 0 ? (
          <p className="mt-2 text-[14px] text-muted">Aucune. Enregistrez-en une depuis la page Rechercher.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {alerts.map((a) => (
              <li key={a.id} className="flex items-center justify-between py-2 text-[14px]">
                <a className="text-primary hover:underline" href={`/rechercher?q=${encodeURIComponent(a.query)}`}>{a.query}</a>
                <button className="text-[13px] text-red-600 hover:underline" onClick={() => removeAlert(a.id)}>Supprimer</button>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-[12px] text-muted">Aucun e-mail n’est envoyé : ce sont des raccourcis de recherche.</p>
      </section>

      <section className="card mt-5 p-6">
        <h2 className="text-[18px] font-medium">Localisation</h2>
        <p className="mt-1 text-[13px] text-muted">{home ? `${home.label || 'Position'} (${home.lat.toFixed(4)}, ${home.lon.toFixed(4)})` : 'Non définie (onglet « Carte & distance »).'}</p>
        <div className="mt-3 flex flex-wrap gap-3">
          {home && <button className="btn-outline" onClick={clearHome}>Effacer ma position</button>}
          {meta.google_geocoding && <button className="btn-outline" disabled={busy} onClick={refine}>{busy ? 'Géocodage…' : 'Affiner les adresses des entreprises (Google)'}</button>}
        </div>
      </section>

      <section className="card mt-5 p-6">
        <h2 className="text-[18px] font-medium">Mes données</h2>
        <p className="mt-1 text-[13px] text-muted">Ton compte, tes sessions, ton profil, ton suivi, tes préférences et tes CV sont conservés dans ton espace privé sur le serveur.</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <a className="btn-outline" href={exportUrl}>Exporter le suivi (CSV)</a>
          <button type="button" className="btn-outline !text-red-600" disabled={busy} onClick={reset}>{busy ? 'Enregistrement…' : 'Réinitialiser le suivi'}</button>
        </div>
      </section>

      <section className="card mt-5 border border-red-200 bg-red-50 p-6">
        <h2 className="text-[18px] font-medium text-red-700">Déconnexion et changement d’utilisateur</h2>
        <p className="mt-1 text-[13px] text-red-700/80">
          {gmailConnected
            ? 'Ton compte Gmail et tes données restent conservés pour ta prochaine connexion.'
            : 'Tes données BookJob sont conservées après la déconnexion.'}
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button className="btn-outline !border-red-300 !text-red-700 hover:bg-red-100" disabled={busy} onClick={signOutAll}>
            {busy ? 'Déconnexion…' : 'Se déconnecter de BookJob'}
          </button>
        </div>
      </section>
    </div>
  )
}
