import { useCallback, useState } from 'react'
import { ArrowLeft, ArrowRight, BriefcaseBusiness, CheckCircle2, Home, MapPin, Search, UserRound } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Modal from './ui/Modal'
import { useStore } from '../store/useStore'

const STEPS = [
  {
    icon: Home,
    title: 'Votre tableau de bord',
    description: 'Retrouvez votre progression, vos candidatures récentes et les entreprises à explorer.',
    action: 'Ouvrir le tableau de bord',
    path: '/tableau-de-bord',
  },
  {
    icon: UserRound,
    title: 'Préparez votre profil',
    description: 'Ajoutez vos coordonnées, vos compétences et un CV dans votre profil. Ces informations vous aideront à préparer vos candidatures.',
    action: 'Compléter mon profil',
    path: '/profil',
  },
  {
    icon: Search,
    title: 'Trouvez une entreprise',
    description: 'Recherchez parmi les entreprises du répertoire, filtrez par secteur ou quartier, puis ouvrez une fiche pour consulter ses coordonnées.',
    action: 'Explorer les entreprises',
    path: '/rechercher',
  },
  {
    icon: MapPin,
    title: 'Repérez les entreprises',
    description: 'La carte affiche les emplacements disponibles et des distances à vol d’oiseau, pas des itinéraires ni des temps de trajet.',
    action: 'Voir la carte',
    path: '/carte',
  },
  {
    icon: BriefcaseBusiness,
    title: 'Postulez et suivez votre démarche',
    description: 'Depuis une fiche entreprise, préparez votre candidature et vérifiez les informations avant l’envoi. Retrouvez ensuite son statut et son historique dans Mes candidatures.',
    action: 'Voir mes candidatures',
    path: '/candidatures',
  },
]

export default function Onboarding() {
  const { setSetting } = useStore()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)

  const finish = useCallback(async (path) => {
    setSaving(true)
    const saved = await setSetting({ onboardingCompleted: true })
    setSaving(false)
    if (saved && path) navigate(path)
  }, [navigate, setSetting])

  const current = STEPS[step]
  const Icon = current.icon

  return (
    <Modal title="Bienvenue sur BookJob" onClose={() => finish()} >
      <div aria-live="polite">
        <div className="mb-5 flex items-center justify-between gap-3">
          <span className="text-[13px] font-medium text-muted">Étape {step + 1} sur {STEPS.length}</span>
          <div className="flex gap-1.5" aria-hidden="true">
            {STEPS.map((item, index) => (
              <span key={item.title} className={`h-1.5 w-8 rounded-full ${index <= step ? 'bg-primary' : 'bg-chip'}`} />
            ))}
          </div>
        </div>
        <div className="rounded-2xl bg-primary-soft p-5">
          <Icon size={28} className="text-primary" aria-hidden="true" />
          <h3 className="mt-4 text-[20px] font-semibold text-ink">{current.title}</h3>
          <p className="mt-2 text-[14px] leading-relaxed text-muted">{current.description}</p>
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <button type="button" disabled={saving} onClick={() => finish()} className="text-[13px] font-medium text-muted underline disabled:opacity-50">
            Passer le guide
          </button>
          <div className="flex gap-2">
            {step > 0 && (
              <button type="button" disabled={saving} onClick={() => setStep((value) => value - 1)} className="btn-outline !py-2.5">
                <ArrowLeft size={16} /> Précédent
              </button>
            )}
            {step < STEPS.length - 1 ? (
              <button type="button" disabled={saving} onClick={() => setStep((value) => value + 1)} className="btn-primary !py-2.5">
                Suivant <ArrowRight size={16} />
              </button>
            ) : (
              <button type="button" disabled={saving} onClick={() => finish(current.path)} className="btn-primary !py-2.5">
                {saving ? 'Enregistrement…' : current.action} <CheckCircle2 size={16} />
              </button>
            )}
          </div>
        </div>
        {step < STEPS.length - 1 && (
          <button type="button" disabled={saving} onClick={() => finish(current.path)} className="mt-3 text-[13px] font-semibold text-primary underline disabled:opacity-50">
            {current.action}
          </button>
        )}
      </div>
    </Modal>
  )
}
