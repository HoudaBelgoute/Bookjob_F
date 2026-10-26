// Constantes d'interface (les données réelles viennent de l'API).
export const TONES = {
  blue: { bg: '#e8f0fb', fg: '#1d5aa6' },
  gold: { bg: '#fbf3dc', fg: '#8a6414' },
  green: { bg: '#e3f5ee', fg: '#1f7a55' },
  violet: { bg: '#efeafb', fg: '#5a43a8' },
}

// Statuts partagés avec l'API de suivi.
export const STATUS_DOT = {
  Brouillon: '#8a97aa',
  'À envoyer': '#c5a45d',
  'Candidature envoyée': '#1d5aa6',
  'En cours de traitement': '#3b82c4',
  'Entretien programmé': '#1f8a5b',
  Acceptée: '#16794c',
  Refusée: '#c0392b',
  'Offre expirée ou candidature annulée': '#6b7686',
}

export const AI_QUESTIONS = [
  'Est-ce que mon profil correspond ?',
  'Quelles compétences me manquent ?',
  'Comment préparer l’entretien ?',
]

export const PRIORITE_LABEL = { A: 'Priorité A', B: 'Priorité B', C: 'Priorité C' }

export function initialsOf(name = '') {
  const w = name.split(/\s+/).filter(Boolean)
  return ((w[0]?.[0] || '') + (w[1]?.[0] || '')).toUpperCase() || '?'
}

export function fmtDate(s) {
  if (!s) return '—'
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
}

// Mini conversion Markdown → HTML (titres, listes, paragraphes) avec échappement.
export function mdToHtml(md = '') {
  const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return md
    .split('\n')
    .map((l) => {
      if (/^# /.test(l)) return `<h1>${esc(l.slice(2))}</h1>`
      if (/^## /.test(l)) return `<h2>${esc(l.slice(3))}</h2>`
      if (/^[-*] /.test(l)) return `<li>${esc(l.slice(2))}</li>`
      if (!l.trim()) return ''
      return `<p>${esc(l)}</p>`
    })
    .join('\n')
}
