// Client minimal de l'API FastAPI (même origine en production, proxy Vite en dev).
async function req(path, { method = 'GET', body, form } = {}) {
  const opts = { method, headers: {} }
  if (form) opts.body = form
  else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  let res
  try {
    res = await fetch(`/api${path}`, { ...opts, cache: 'no-store', credentials: 'same-origin' })
  } catch {
    throw new Error('Serveur injoignable. Vérifiez que le backend est démarré.')
  }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new Event('bookjob-auth-required'))
    }
    let detail = `Erreur ${res.status}`
    try {
      const j = await res.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

const qs = (params) => {
  const u = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '' || v === false) return
    if (Array.isArray(v)) v.forEach((x) => u.append(k, x))
    else u.append(k, v)
  })
  const s = u.toString()
  return s ? `?${s}` : ''
}

export const api = {
  authStatus: () => req('/auth/status'),
  login: (email, password) => req('/auth/login', { method: 'POST', body: { email, password } }),
  register: (full_name, email, password, registration_key) => req('/auth/register', {
    method: 'POST',
    body: { full_name, email, password, registration_key },
  }),
  logout: () => req('/auth/logout', { method: 'POST' }),
  googleStatus: () => req('/google/status'),
  disconnectGoogle: () => req('/google/disconnect', { method: 'POST' }),
  meta: () => req('/meta'),
  companies: (params = {}) => req(`/companies${qs(params)}`),
  company: (id) => req(`/companies/${encodeURIComponent(id)}`),
  discoverCompanyEmails: (id) => req(`/companies/${encodeURIComponent(id)}/contact-emails`, { method: 'POST' }),
  toggleFavorite: (id) => req(`/favorites/${encodeURIComponent(id)}`, { method: 'POST' }),
  favorites: () => req('/favorites'),
  home: () => req('/home'),
  dataQuality: () => req('/data-quality'),
  tracking: () => req('/tracking'),
  trackingEvents: (id) => req(`/tracking/${encodeURIComponent(id)}/events`),
  trackingEmails: (id) => req(`/tracking/${encodeURIComponent(id)}/emails`),
  applicationSendStatus: (id) => req(`/tracking/${encodeURIComponent(id)}/send-status`),
  addTracking: (b) => req('/tracking', { method: 'POST', body: b }),
  patchTracking: (id, b) => req(`/tracking/${encodeURIComponent(id)}`, { method: 'PATCH', body: b }),
  deleteTracking: (id) => req(`/tracking/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  apply: (form) => req('/tracking/apply', { method: 'POST', form }),
  sendApplication: (id, form) => req(`/tracking/${encodeURIComponent(id)}/send`, { method: 'POST', form }),
  profile: () => req('/profile'),
  saveProfile: (patch) => req('/profile', { method: 'PUT', body: patch }),
  uploadAvatar: (file) => {
    const f = new FormData()
    f.append('file', file)
    return req('/profile/avatar', { method: 'POST', form: f })
  },
  deleteAvatar: () => req('/profile/avatar', { method: 'DELETE' }),
  cvs: () => req('/cvs'),
  uploadCv: (file) => {
    const f = new FormData()
    f.append('file', file)
    return req('/cvs', { method: 'POST', form: f })
  },
  mainCv: (id) => req(`/cvs/${id}/main`, { method: 'POST' }),
  deleteCv: (id) => req(`/cvs/${id}`, { method: 'DELETE' }),
  genCv: (b) => req('/generate/cv', { method: 'POST', body: b }),
  genLetter: (b) => req('/generate/letter', { method: 'POST', body: b }),
  geocode: (adresse) => req('/geocode', { method: 'POST', body: { adresse } }),
  setHome: (b) => req('/home', { method: 'PUT', body: b }),
  clearHome: () => req('/home', { method: 'DELETE' }),
  geocodeCompanies: () => req('/geocode/companies', { method: 'POST' }),
  chats: () => req('/chats'),
  newChat: () => req('/chats', { method: 'POST' }),
  deleteChat: (id) => req(`/chats/${id}`, { method: 'DELETE' }),
  chat: (b) => req('/chat', { method: 'POST', body: b }),
  alerts: () => req('/alerts'),
  addAlert: (query) => req('/alerts', { method: 'POST', body: { query } }),
  deleteAlert: (id) => req(`/alerts/${id}`, { method: 'DELETE' }),
  settings: () => req('/settings'),
  saveSettings: (b) => req('/settings', { method: 'PUT', body: b }),
  dashboard: () => req('/dashboard'),
  notifications: () => req('/notifications'),
  stats: (start, end) => req(`/stats${qs({ start, end })}`),
  emailSyncStatus: () => req('/email-sync/status'),
  runEmailSync: () => req('/email-sync/run', { method: 'POST' }),
  emailSyncReviews: () => req('/email-sync/reviews'),
  resolveEmailSyncReview: (messageId, body) => req(`/email-sync/reviews/${encodeURIComponent(messageId)}`, {
    method: 'POST',
    body,
  }),
  resetTracking: () => req('/reset/tracking', { method: 'POST' }),
}

export const cvUrl = (trackId) => `/api/tracking/${encodeURIComponent(trackId)}/cv`
export const libCvUrl = (id) => `/api/cvs/${id}/file`
export const exportUrl = '/api/export/suivi.csv'
