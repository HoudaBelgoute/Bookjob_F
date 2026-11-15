const SENT_STATUSES = new Set([
  'Candidature envoyée',
  'En cours de traitement',
  'Entretien programmé',
  'Acceptée',
  'Refusée',
])

function hasValidDate(value) {
  if (typeof value !== 'string') return false
  const date = value.trim()
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:$|[T\s])/.exec(date)
  if (!match || !Number.isFinite(Date.parse(date))) return false

  const dateOnly = match.slice(1).join('-')
  return new Date(`${dateOnly}T00:00:00Z`).toISOString().slice(0, 10) === dateOnly
}

export function countSentApplications(applications) {
  return applications.filter((application) => (
    SENT_STATUSES.has(application.statut)
    && hasValidDate(application.date_candidature)
  )).length
}
