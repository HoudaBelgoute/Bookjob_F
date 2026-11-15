import assert from 'node:assert/strict'
import { test } from 'node:test'
import { countSentApplications } from './applicationStats.js'

test('counts only dated applications that reached a sent status', () => {
  const applications = [
    { statut: 'Candidature envoyée', date_candidature: '2026-11-10' },
    { statut: 'Entretien programmé', date_candidature: '2026-11-11' },
    { statut: 'Refusée', date_candidature: '2026-11-12' },
    { statut: 'Brouillon', date_candidature: '2026-11-13' },
    { statut: 'À envoyer', date_candidature: '' },
    { statut: 'Offre expirée ou candidature annulée', date_candidature: '2026-11-14' },
    { statut: 'Candidature envoyée', date_candidature: 'inconnue' },
    { statut: 'Candidature envoyée', date_candidature: '2026-02-30' },
  ]

  assert.equal(countSentApplications(applications), 3)
})
