import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { ArrowRight, BriefcaseBusiness, Check, Eye, EyeOff, FileText, MapPin, Search } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useStore } from '../store/useStore'
import '../styles/auth.css'

const AUTH_CHANNEL_NAME = 'bookjob-auth'
const AUTH_STORAGE_KEY = 'bookjob-auth-change'
const AuthContext = createContext({ required: true, user: null })
const AUTH_PARTICLE_COUNT = 64

const authParticles = Array.from({ length: AUTH_PARTICLE_COUNT }, (_, index) => {
  const seed = index + 1
  const positionX = (seed * 47 + seed * seed * 13) % 100
  const positionY = (seed * 71 + seed * seed * 7) % 100
  const delay = -((seed * 1.73) % 8)
  const duration = 3.2 + ((seed * 11) % 40) / 10

  return {
    id: seed,
    style: {
      left: `${positionX}%`,
      top: `${positionY}%`,
      '--particle-delay': `${delay}s`,
      '--particle-duration': `${duration}s`,
    },
  }
})

export const useAuth = () => useContext(AuthContext)

function AuthBrandPanel() {
  const highlights = [
    { icon: FileText, label: 'Préparez vos CV' },
    { icon: Search, label: 'Explorez les offres' },
    { icon: MapPin, label: 'Suivez votre parcours' },
  ]

  return (
    <section className="auth-brand-panel">
      <div className="auth-sky" aria-hidden="true">
        {authParticles.map(({ id, style }) => (
          <span
            key={id}
            className={`auth-particle${id % 6 === 0 ? ' auth-particle--spark' : ''}`}
            style={style}
          />
        ))}
        <svg className="auth-orbit" viewBox="0 0 240 240" fill="none">
          <circle cx="120" cy="120" r="104" />
          <circle cx="120" cy="120" r="77" />
          <path d="M120 16a104 104 0 0 1 90 52" />
          <path d="M194 158a86 86 0 0 1-72 38" />
          <circle className="auth-orbit-star" cx="210" cy="68" r="4" />
          <circle className="auth-orbit-star auth-orbit-star--gold" cx="48" cy="168" r="3" />
        </svg>
      </div>
      <Link to="/" className="auth-brand" aria-label="BookJob, retour à l’accueil">
        <span className="auth-brand-mark"><BriefcaseBusiness size={26} /></span>
        <span className="auth-brand-word">Book<span>Job</span><small>VOTRE PARCOURS, VOTRE ESPACE</small></span>
      </Link>
      <div className="auth-brand-content">
        <div className="auth-highlights">
          {highlights.map(({ icon: Icon, label }) => (
            <div className="auth-highlight" key={label}>
              <Icon size={22} />
              <span>{label}</span>
            </div>
          ))}
        </div>
        <p className="auth-kicker">OPPORTUNITÉS • CANDIDATURES • PARCOURS</p>
        <h2>De nouvelles opportunités, <span>près de chez vous.</span></h2>
        <p className="auth-brand-description">
          Découvrez les entreprises de Marrakech et organisez votre recherche d’emploi, de stage ou d’alternance.
        </p>
        <div className="auth-benefits" aria-label="Les atouts de BookJob">
          <span><Search size={18} /> Trouvez des offres adaptées</span>
          <span><BriefcaseBusiness size={18} /> Découvrez les entreprises locales</span>
          <span><Check size={18} /> Suivez vos démarches simplement</span>
        </div>
      </div>
      <p className="auth-brand-credit">
        Marrakech, Maroc <span>·</span> Un projet réalisé par Houda Belgoute
        <br />
        Photo : <a href="https://commons.wikimedia.org/wiki/File:Day_2_-_sunset_at_the_Kutubiyya_Mosque,_Marrakech,_Morocco_2010_-_Flickr_-_ambabheg.jpg" target="_blank" rel="noopener noreferrer">Forbes Johnston</a>
        {' · '}
        <a href="https://creativecommons.org/licenses/by/2.0/" target="_blank" rel="noopener noreferrer">CC BY 2.0</a>
      </p>
    </section>
  )
}

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
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const registering = pathname === '/inscription'
  const [status, setStatus] = useState(null)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [registrationKey, setRegistrationKey] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
    const requests = new Set()
    const refreshStatus = async () => {
      const controller = new AbortController()
      requests.add(controller)
      const timeout = window.setTimeout(() => controller.abort(), 10000)
      try {
        const next = await api.authStatus(controller.signal)
        if (!active) return
        updateStatus(next)
      } catch (e) {
        if (active) setError(e.message)
      } finally {
        window.clearTimeout(timeout)
        requests.delete(controller)
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
      requests.forEach((controller) => controller.abort())
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
    return (
      <main className="auth-page">
        <AuthBrandPanel />
        <section className="auth-form-side">
          <div className="auth-card">
            <Link to="/" className="auth-back-link">← Retour à l’accueil</Link>
            <p className="eyebrow mt-8">Votre espace BookJob</p>
            <h1 className="auth-title">Connexion momentanément indisponible</h1>
            <p role="alert" className="mt-3 text-sm leading-6 text-muted">{error}</p>
            <div className="mt-6 flex flex-wrap gap-3">
            <button type="button" className="btn-primary" onClick={() => window.location.reload()}>
              Réessayer
            </button>
            <Link to="/" className="btn-outline">Retour à l’accueil</Link>
            </div>
          </div>
        </section>
      </main>
    )
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
    <main className="auth-page">
      <AuthBrandPanel />
      <section className="auth-form-side">
        <div className="auth-card">
          <Link to="/" className="auth-back-link">← Retour à l’accueil</Link>
          <div className="auth-tabs" role="group" aria-label="Choisir le mode d’accès">
            <button
              type="button"
              aria-pressed={!registering}
              onClick={() => {
                setError('')
                setPassword('')
                setConfirmation('')
                navigate('/connexion')
              }}
            >
              Se connecter
            </button>
            <button
              type="button"
              aria-pressed={registering}
              onClick={() => {
                setError('')
                setPassword('')
                setConfirmation('')
                navigate('/inscription')
              }}
            >
              S’inscrire
            </button>
          </div>
          <h1 className="auth-title">{registering ? 'Créer un compte' : 'Ravi de vous revoir'}</h1>
          <p className="auth-subtitle">
            {registering
              ? 'Créez votre espace personnel pour organiser votre recherche.'
              : 'Connectez-vous pour retrouver votre profil et vos candidatures.'}
          </p>
          {googleError && <p role="alert" className="auth-feedback">{googleError}</p>}
          {status.google_login && (
            <>
              <a href="/api/auth/google" className="auth-google-button">
                <span className="auth-google-mark" aria-hidden="true">G</span>
                Continuer avec Google
              </a>
              <div className="auth-divider"><span>ou avec e-mail</span></div>
            </>
          )}
          <form onSubmit={submit} className="auth-form">
            {registering && (
              <label className="auth-field">
                Nom complet
                <input
                  autoComplete="name"
                  required
                  maxLength={120}
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  placeholder="Votre nom complet"
                />
              </label>
            )}
            <label className="auth-field">
              Adresse e-mail
              <input
                autoFocus
                required
                type="email"
                autoComplete="email"
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="vous@exemple.com"
              />
            </label>
            <label className="auth-field">
              Mot de passe
              <span className="auth-password-wrap">
                <input
                  required
                  type={showPassword ? 'text' : 'password'}
                  minLength={registering ? 10 : 1}
                  maxLength={256}
                  autoComplete={registering ? 'new-password' : 'current-password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Votre mot de passe"
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </span>
              {registering && (
                <span className="auth-password-hint">
                  <Check size={14} className={password.length >= 10 ? 'is-valid' : ''} />
                  10 caractères minimum
                </span>
              )}
            </label>
            {registering && (
              <>
                <label className="auth-field">
                  Confirmer le mot de passe
                  <input
                    required
                    type="password"
                    minLength={10}
                    maxLength={256}
                    autoComplete="new-password"
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    placeholder="Confirmez votre mot de passe"
                  />
                </label>
                {status.registration_key_required && (
                  <label className="auth-field">
                    Clé d’invitation
                    <input
                      required
                      type="password"
                      autoComplete="off"
                      value={registrationKey}
                      onChange={(event) => setRegistrationKey(event.target.value)}
                      placeholder="Votre clé d’invitation"
                    />
                  </label>
                )}
              </>
            )}
            {error && <p role="alert" className="auth-feedback">{error}</p>}
            <button disabled={busy} className="auth-submit">
              {busy
                ? 'Patiente…'
                : <>{registering ? 'Créer mon compte' : 'Se connecter'} <ArrowRight size={18} /></>}
            </button>
          </form>
          {status.google_login && (
            <p className="auth-privacy-note">
              Google partage uniquement votre nom et votre adresse e-mail vérifiée. L’accès à Gmail reste facultatif.
            </p>
          )}
          <p className="auth-switch-prompt">
            {registering ? 'Vous avez déjà un compte ?' : 'Vous n’avez pas encore de compte ?'}
            {' '}
            <button
              type="button"
              onClick={() => {
                setError('')
                setPassword('')
                setConfirmation('')
                navigate(registering ? '/connexion' : '/inscription')
              }}
            >
              {registering ? 'Se connecter' : 'Créer un compte'}
            </button>
          </p>
          <div className="auth-legal">
            <span>Vos informations restent privées et associées à votre compte.</span>
          </div>
        </div>
      </section>
    </main>
  )
}
