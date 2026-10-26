import { create } from 'zustand'
import { api } from '../api'

let userDataEpoch = 0

export const useStore = create((set, get) => ({
  ready: false,
  error: null,
  toast: null,
  meta: null,
  profile: {},
  avatarUrl: null,
  completion: { percent: 0, items: [] },
  skills: [],
  favorites: [],
  tracking: [],
  counts: {},
  relances: [],
  cvs: [],
  chats: [],
  activeChat: null,
  chatOpen: false,
  home: null,
  settings: { useProfileForAI: true },
  alerts: [],
  activeCompanyId: null,
  allCompanies: [],

  notify: (message) => {
    const id = Date.now()
    set({ toast: { id, message } })
    setTimeout(() => get().toast?.id === id && set({ toast: null }), 3200)
  },

  resetForLogout: () => {
    userDataEpoch += 1
    set({
      ready: false,
      error: null,
      toast: null,
      meta: null,
      profile: {},
      avatarUrl: null,
      completion: { percent: 0, items: [] },
      skills: [],
      favorites: [],
      tracking: [],
      counts: {},
      relances: [],
      cvs: [],
      chats: [],
      activeChat: null,
      chatOpen: false,
      home: null,
      settings: { useProfileForAI: true },
      alerts: [],
      activeCompanyId: null,
      allCompanies: [],
    })
  },

  // Exécute un appel API et notifie l'erreur au lieu de planter l'écran.
  safe: async (fn, okMsg) => {
    const epoch = userDataEpoch
    try {
      const r = await fn()
      if (epoch !== userDataEpoch) return null
      if (okMsg) get().notify(okMsg)
      return r
    } catch (e) {
      if (epoch !== userDataEpoch) return null
      get().notify(e.message)
      return null
    }
  },

  init: async () => {
    const epoch = userDataEpoch
    try {
      const [meta, prof, fav, tr, cvs, chats, home, settings, alerts, comp] = await Promise.all([
        api.meta(), api.profile(), api.favorites(), api.tracking(), api.cvs(),
        api.chats(), api.home(), api.settings(), api.alerts(),
        api.companies({ limit: 500, sort: 'nom' }),
      ])
      if (epoch !== userDataEpoch) return
      set({
        ready: true, error: null, meta, profile: prof.profile, avatarUrl: prof.avatar_url || null, completion: prof.completion, skills: prof.skills,
        favorites: fav.favorites, tracking: tr.items, counts: tr.counts, relances: tr.relances_dues, cvs: cvs.items,
        chats: chats.items, activeChat: chats.items[0]?.id || null, home: home.home, settings, alerts: alerts.items,
        allCompanies: comp.items,
      })
    } catch (e) {
      if (epoch !== userDataEpoch) return
      set({ error: e.message })
    }
  },

  refreshTracking: async () => {
    const epoch = userDataEpoch
    const tr = await api.tracking()
    if (epoch !== userDataEpoch) return
    set({ tracking: tr.items, counts: tr.counts, relances: tr.relances_dues })
  },
  refreshCompanies: async () => {
    const comp = await api.companies({ limit: 500, sort: 'nom' })
    set({ allCompanies: comp.items })
  },

  refreshCvs: async () => {
    const epoch = userDataEpoch
    const r = await api.cvs()
    if (epoch === userDataEpoch) set({ cvs: r.items })
  },

  openCompany: (id) => set({ activeCompanyId: id }),
  setChatOpen: (open) => set({ chatOpen: open }),
  // Ouvre le petit chatbot, éventuellement avec une entreprise comme contexte.
  askAssistant: (companyId) => set((s) => ({ chatOpen: true, activeCompanyId: companyId === undefined ? s.activeCompanyId : companyId })),

  toggleFavorite: async (id) => {
    const r = await get().safe(() => api.toggleFavorite(id))
    if (!r) return
    set({ favorites: r.favorites })
    get().notify(r.favorite ? 'Ajouté aux favoris' : 'Retiré des favoris')
  },

  addToTracking: async (company_id) => {
    const r = await get().safe(() => api.addTracking({ company_id }), 'Ajouté au suivi')
    if (r) await get().refreshTracking()
    return r
  },
  addExternal: async (b) => {
    const r = await get().safe(() => api.addTracking(b), 'Offre ajoutée au suivi')
    if (r) await get().refreshTracking()
    return r
  },
  updateTracking: async (id, patch, msg) => {
    const r = await get().safe(() => api.patchTracking(id, patch), msg)
    if (r) await get().refreshTracking()
    return r
  },
  removeTracking: async (id) => {
    const r = await get().safe(() => api.deleteTracking(id), 'Candidature supprimée')
    if (r) await get().refreshTracking()
  },
  apply: async (form) => {
    const r = await get().safe(() => api.apply(form), 'Candidature préparée. Confirmez l’envoi auprès de l’employeur.')
    if (r) await get().refreshTracking()
    return r
  },
  sendApplication: async (id, message) => {
    const r = await get().safe(() => api.sendApplication(id, message))
    if (r) {
      get().notify('E-mail de confirmation envoyé à ton Gmail')
    }
    return r
  },
  applicationSendStatus: async (id) => get().safe(() => api.applicationSendStatus(id)),

  saveProfile: async (patch) => {
    const r = await get().safe(() => api.saveProfile(patch), 'Profil enregistré')
    if (r) set({ profile: r.profile, completion: r.completion, skills: r.skills })
    return r
  },
  uploadAvatar: async (file) => {
    const r = await get().safe(() => api.uploadAvatar(file), 'Photo de profil mise à jour')
    if (r) set({ avatarUrl: r.avatar_url })
    return r
  },
  removeAvatar: async () => {
    const r = await get().safe(() => api.deleteAvatar(), 'Photo de profil supprimée')
    if (r) set({ avatarUrl: null })
    return r
  },

  uploadCv: async (file) => {
    const r = await get().safe(() => api.uploadCv(file), 'CV importé')
    if (r) set({ cvs: r.items })
    return r
  },
  mainCv: async (id) => {
    const r = await get().safe(() => api.mainCv(id), 'CV principal mis à jour')
    if (r) set({ cvs: r.items })
    return r
  },
  removeCv: async (id) => {
    const r = await get().safe(() => api.deleteCv(id), 'CV supprimé')
    if (r) set({ cvs: r.items })
    return r
  },

  setHome: async (h) => {
    const r = await get().safe(() => api.setHome(h), 'Localisation enregistrée')
    if (r) set({ home: r.home })
    return r
  },
  clearHome: async () => {
    const r = await get().safe(() => api.clearHome(), 'Localisation effacée')
    if (r) set({ home: null })
  },

  newChat: async () => {
    const ch = await get().safe(() => api.newChat())
    if (ch) set({ chats: [ch, ...get().chats], activeChat: ch.id })
  },
  selectChat: (id) => set({ activeChat: id }),
  removeChat: async (id) => {
    const r = await get().safe(() => api.deleteChat(id))
    if (r) set({ chats: r.items, activeChat: r.items[0]?.id || null })
  },
  sendMessage: async (message, company_id) => {
    const { activeChat, settings } = get()
    const r = await get().safe(() => api.chat({ chat_id: activeChat, message, company_id, use_profile: settings.useProfileForAI }))
    if (!r) return null
    const exists = get().chats.some((c) => c.id === r.chat.id)
    set({
      chats: exists ? get().chats.map((c) => (c.id === r.chat.id ? r.chat : c)) : [r.chat, ...get().chats],
      activeChat: r.chat.id,
    })
    return r
  },

  setSetting: async (patch) => {
    const r = await get().safe(() => api.saveSettings(patch))
    if (r) set({ settings: r })
  },
  addAlert: async (query) => {
    const r = await get().safe(() => api.addAlert(query), 'Recherche enregistrée')
    if (r) set({ alerts: r.items })
  },
  removeAlert: async (id) => {
    const r = await get().safe(() => api.deleteAlert(id))
    if (r) set({ alerts: r.items })
  },
}))
