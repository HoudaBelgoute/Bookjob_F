const REQUIRED_CV_FIELDS = [
  { field: 'nom', label: 'Nom complet', href: '/profil#infos-personnelles' },
  { field: 'titre', label: 'Poste visé', href: '/profil#infos-personnelles' },
  { field: 'email', label: 'Adresse e-mail valide', href: '/profil#infos-personnelles' },
  { field: 'tel', label: 'Téléphone valide', href: '/profil#infos-personnelles' },
  { field: 'ville', label: 'Ville', href: '/profil#infos-personnelles' },
  { field: 'formation', label: 'Formation', href: '/profil#formation' },
  { field: 'experiences', label: 'Expériences ou stages (ou indiquez « aucune »)', href: '/profil#experiences' },
  { field: 'competences', label: 'Compétences techniques', href: '/profil#competences' },
  { field: 'langues', label: 'Langues et niveaux', href: '/profil#langues' },
]

export function getMissingCvProfileFields(profile) {
  return REQUIRED_CV_FIELDS.filter(({ field }) => {
    const value = String(profile?.[field] || '').trim()
    if (!value) return true
    if (field === 'email') return !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)
    if (field === 'tel') return value.replace(/\D/g, '').length < 8
    return false
  })
}
