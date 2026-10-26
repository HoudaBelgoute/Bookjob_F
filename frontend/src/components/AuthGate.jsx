import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useStore } from '../store/useStore'

const AUTH_CHANNEL_NAME = 'bookjob-auth'
const AUTH_STORAGE_KEY = 'bookjob-auth-change'
const AuthContext = createContext({ required: true, user: null })

export const useAuth = () => useContext(AuthContext)

function publishAuthChange(channel) {
  if (channel) {
    channel.postMessage({ type: 'session-changed' })
    return
  }
  try {
    window.localStorage.setItem(AUTH_STORAGE_KEY, crypto.randomUUID())
  } catch (error) {
    console.error('BookJob could not notify other tabs about an authentication change.', error)
  }
}

export default function AuthGate({ children }) {
  const [status, setStatus] = useState(null)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [registrationKey, setRegistrationKey] = useState('')
  const [registering, setRegistering] = useState(false)
  const [error, setError] = useState('')
  const [googleError, setGoogleError] = useState('')
  const [busy, setBusy] = useState(false)
  const resetForLogout = useStore((state) => state.resetForLogout)
  const statusRef = useRef(null)
  const authChannelRef = useRef(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const message = params.get('erreur_google')
    if (message) {
      setGoogleError(message)
      window.history.replaceState(null, '', window.location.pathname)
    }
  }, [])

  const updateStatus = useCallback((next) => {
    const previous = statusRef.current
    const accountChanged = previous?.authenticated && next.authenticated
      && previous.user?.id !== next.user?.id
    if (!next.authenticated || accountChanged) resetForLogout()
    statusRef.current = next
    setStatus(next)
  }, [resetForLogout])

  const signOut = useCallback(async () => {
    updateStatus({
      ...statusRef.current,
      required: true,
      authenticated: false,
      user: null,
    })
    try {
      const result = await api.logout()
      publishAuthChange(authChannelRef.current)
      if (result.warning) window.alert(result.warning)
      window.location.replace('/')
      return result
    } catch (e) {
      setError(e.message)
      throw e
    }
  }, [updateStatus])

  useEffect(() => {
    let active = true
    const refreshStatus = async () => {
      try {
        const next = await api.authStatus()
        if (!active) return
        updateStatus(next)
      } catch (e) {
        if (active) setError(e.message)
      }
    }
    const requireLogin = () => {
      updateStatus({
        ...statusRef.current,
        required: true,
        authenticated: false,
        user: null,
      })
    }
    const onStorage = (event) => {
      if (event.key === AUTH_STORAGE_KEY && event.newValue) invalidateAndRefresh()
    }
    const invalidateAndRefresh = () => {
      statusRef.current = null
      setStatus(null)
      resetForLogout()
      refreshStatus()
    }
    const onVisibilityChange = () => {
      if (!document.hidden) refreshStatus()
    }
    const onPageShow = (event) => {
      if (event.persisted) {
        statusRef.current = null
        setStatus(null)
        resetForLogout()
        refreshStatus()
      }
    }
    const channel = typeof BroadcastChannel === 'function'
      ? new BroadcastChannel(AUTH_CHANNEL_NAME)
      : null
    authChannelRef.current = channel
    channel?.addEventListener('message', (event) => {
      if (event.data?.type === 'session-changed') invalidateAndRefresh()
    })
    refreshStatus()
    window.addEventListener('bookjob-auth-required', requireLogin)
    window.addEventListener('pageshow', onPageShow)
    window.addEventListener('focus', refreshStatus)
    window.addEventListener('storage', onStorage)
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      active = false
      channel?.close()
      authChannelRef.current = null
      window.removeEventListener('bookjob-auth-required', requireLogin)
      window.removeEventListener('pageshow', onPageShow)
      window.removeEventListener('focus', refreshStatus)
      window.removeEventListener('storage', onStorage)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [resetForLogout, updateStatus])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      let result
      if (registering) {
        if (password !== confirmation) throw new Error('Les deux mots de passe ne correspondent pas.')
        result = await api.register(fullName, email, password, registrationKey)
      } else {
        result = await api.login(email, password)
      }
      updateStatus({
        required: true,
        authenticated: true,
        user: result.user,
        registration_open: true,
        registration_key_required: status?.registration_key_required || false,
      })
      publishAuthChange(authChannelRef.current)
      setPassword('')
      setConfirmation('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !status) {
    return <div className="flex min-h-screen items-center justify-center p-6 text-sm text-red-700">{error}</div>
  }
  if (!status) return <div className="p-10 text-muted">Vérification de la connexion…</div>
  if (status.authenticated) {
    return (
      <AuthContext.Provider value={{ required: true, user: status.user, signOut }}>
        <div key={status.user.id}>{children}</div>
      </AuthContext.Provider>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface p-5">
      <form onSubmit={submit} className="card w-full max-w-md space-y-4 p-8">
        <p className="eyebrow">BookJob</p>
        <h1 className="text-2xl font-semibold text-navy-900">{registering ? 'Créer mon compte' : 'Connexion'}</h1>
        <p className="text-sm text-muted">
          {registering
            ? 'Crée un compte personnel. Tes candidatures, ton profil et tes CV seront isolés des autres comptes.'
            : 'Connecte-toi pour retrouver ton profil et tes candidatures.'}
        </p>
        <label className="block text-sm font-semibold">
          Adresse e-mail
          <input
            autoFocus
            required
            type="email"
            autoComplete="email"
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-2 w-full rounded-xl border border-line bg-white px-3.5 py-3 text-sm outline-none focus:border-primary"
          />
        </label>
        <label className="block text-sm font-semibold">
          Mot de passe
          <input
            required
            type="password"
            minLength={registering ? 10 : 1}
            maxLength={256}
            autoComplete={registering ? 'new-password' : 'current-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-2 w-full rounded-xl border border-line bg-white px-3.5 py-3 text-sm outline-none focus:border-primary"
          />
          {registering && <span className="mt-1 block text-xs font-normal text-muted">10 caractères minimum.</span>}
        </label>
        {registering && (
          <>
            <label className="block text-sm font-semibold">
              Nom complet
              <input
                autoComplete="name"
                required
                maxLength={120}
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                className="mt-2 w-full rounded-xl border border-line bg-white px-3.5 py-3 text-sm outline-none focus:border-primary"
              />
            </label>
            <label className="block text-sm font-semibold">
              Confirmer le mot de passe
              <input
                required
                type="password"
                minLength={10}
                maxLength={256}
                autoComplete="new-password"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                className="mt-2 w-full rounded-xl border border-line bg-white px-3.5 py-3 text-sm outline-none focus:border-primary"
              />
            </label>
            {status.registration_key_required && (
              <label className="block text-sm font-semibold">
                Clé d’invitation
                <input
                  required
                  type="password"
                  autoComplete="off"
                  value={registrationKey}
                  onChange={(event) => setRegistrationKey(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-line bg-white px-3.5 py-3 text-sm outline-none focus:border-primary"
                />
              </label>
            )}
          </>
        )}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        {googleError && !error && <p role="alert" className="text-sm text-red-600">{googleError}</p>}
        <button disabled={busy} className="btn-primary w-full justify-center">
          {busy ? 'Patiente…' : registering ? 'Créer mon compte' : 'Se connecter'}
        </button>
        {status.google_login && (
          <>
            <div className="flex items-center gap-3 text-xs text-muted">
              <span className="h-px flex-1 bg-line" />ou<span className="h-px flex-1 bg-line" />
            </div>
            <a href="/api/auth/google" className="btn-outline w-full justify-center">
              Continuer avec Google
            </a>
            <p className="text-xs text-muted">
              Google transmet uniquement ton nom et ton adresse e-mail vérifiée. L’accès à Gmail reste une
              autorisation séparée, demandée seulement si tu choisis d’envoyer tes candidatures depuis BookJob.
            </p>
          </>
        )}
        <button
          type="button"
          onClick={() => {
            setRegistering((value) => !value)
            setError('')
            setPassword('')
            setConfirmation('')
          }}
          className="w-full text-sm font-medium text-primary hover:underline"
        >
          {registering ? 'J’ai déjà un compte' : 'Créer un compte'}
        </button>
      </form>
    </main>
  )
}
