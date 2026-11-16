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

export default function SettingsPage() {
  const { settings, setSetting, alerts, removeAlert, meta, home, clearHome, notify, refreshTracking, refreshCompanies } = useStore()
  const { signOut: authSignOut } = useAuth()
  const [busy, setBusy] = useState(false)
  const [gmailConnected, setGmailConnected] = useState(Boolean(meta?.email?.connected))
  const [aiKeyStatus, setAiKeyStatus] = useState(null)
  const [aiKeyInput, setAiKeyInput] = useState('')
  const [aiKeyBusy, setAiKeyBusy] = useState(false)
  const [aiKeyError, setAiKeyError] = useState('')

  useEffect(() => {
    setGmailConnected(Boolean(meta?.email?.connected))
  }, [meta?.email?.connected])

  useEffect(() => {
    api.aiKeyStatus()
      .then(setAiKeyStatus)
      .catch((error) => setAiKeyError(error.message || 'Impossible de charger le statut de la clé IA.'))
  }, [])

  const saveAiKey = async (event) => {
    event.preventDefault()
    setAiKeyBusy(true)
    setAiKeyError('')
    try {
      setAiKeyStatus(await api.saveAiKey(aiKeyInput))
      setAiKeyInput('')
      notify('Clé Groq vérifiée et enregistrée de façon chiffrée')
    } catch (error) {
      setAiKeyError(error.message || 'Impossible de vérifier cette clé.')
    } finally {
      setAiKeyBusy(false)
    }
  }

  const removeAiKey = async () => {
    setAiKeyBusy(true)
    setAiKeyError('')
    try {
      setAiKeyStatus(await api.deleteAiKey())
      notify('Clé personnelle supprimée')
    } catch (error) {
      setAiKeyError(error.message || 'Impossible de supprimer cette clé.')
    } finally {
      setAiKeyBusy(false)
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
        <div className="py-4 text-[13px] text-muted">
          <strong className="text-ink">Mode IA :</strong>{' '}
          {aiKeyStatus?.mode === 'personal' ? 'Clé Groq personnelle chiffrée' :
            aiKeyStatus?.mode === 'server' ? 'Configuration serveur partagée' :
              aiKeyStatus?.mode === 'unavailable' ? 'Clé personnelle indisponible : vérifiez la configuration de chiffrement' :
                aiKeyStatus?.mode === 'none' ? 'Mode modèle sans fournisseur externe' : 'Chargement…'}
          <p className="mt-1">Seul Groq est pris en charge. La clé n’est jamais renvoyée au navigateur; une clé personnelle est chiffrée au repos. Sans clé personnelle, la configuration serveur est utilisée si elle existe.</p>
        </div>
        {aiKeyStatus?.encryption_available && (
          <form onSubmit={saveAiKey} className="space-y-3 py-4">
            <label htmlFor="groq-api-key" className="block text-[13px] font-semibold">Clé API Groq personnelle</label>
            <div className="flex flex-wrap gap-2">
              <input
                id="groq-api-key"
                type="password"
                autoComplete="new-password"
                value={aiKeyInput}
                onChange={(event) => setAiKeyInput(event.target.value)}
                placeholder={aiKeyStatus.personal_key_configured ? 'Remplacer la clé enregistrée' : 'Coller une clé Groq'}
                className="min-w-[220px] flex-1 rounded-xl border border-line bg-white px-3.5 py-2.5 text-[14px] outline-none focus:border-primary"
                aria-describedby="groq-api-key-help"
              />
              <button type="submit" className="btn-primary" disabled={aiKeyBusy || !aiKeyInput.trim()}>
                {aiKeyBusy ? 'Vérification…' : 'Vérifier et enregistrer'}
              </button>
            </div>
            <p id="groq-api-key-help" className="text-[12px] text-muted">
              {aiKeyStatus.personal_key_configured
                ? `Enregistrée : ${aiKeyStatus.masked_key}. Enregistrer une nouvelle clé la remplacera.`
                : 'La clé est vérifiée auprès de Groq avant son enregistrement chiffré.'}
            </p>
            {aiKeyStatus.personal_key_configured && (
              <button type="button" className="text-[13px] font-semibold text-red-600 underline" disabled={aiKeyBusy} onClick={removeAiKey}>
                Supprimer ma clé et revenir au mode serveur
              </button>
            )}
          </form>
        )}
        {aiKeyError && <p role="alert" className="pb-4 text-[13px] text-red-700">{aiKeyError}</p>}
        {aiKeyStatus && !aiKeyStatus.encryption_available && (
          <div className="space-y-2 py-4">
            <p className="text-[13px] text-muted">
              L’enregistrement d’une clé personnelle n’est pas activé sur ce serveur. Les paramètres peuvent être revus par l’administrateur; aucune nouvelle clé n’est stockée sans chiffrement.
            </p>
            {aiKeyStatus?.personal_key_configured && (
              <button type="button" className="text-[13px] font-semibold text-red-600 underline" disabled={aiKeyBusy} onClick={removeAiKey}>
                Supprimer la clé personnelle indisponible
              </button>
            )}
          </div>
        )}
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
