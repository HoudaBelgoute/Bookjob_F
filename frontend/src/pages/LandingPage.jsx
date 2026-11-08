import {
  ArrowDown,
  ArrowRight,
  BarChart3,
  Bookmark,
  BriefcaseBusiness,
  Check,
  FileText,
  Github,
  GraduationCap,
  Linkedin,
  MapPin,
  Search,
  Sparkles,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import '../styles/landing.css'

const tools = [
  {
    icon: Search,
    title: 'Trouver des opportunités',
    description: 'Explorez les entreprises et les offres, puis repérez celles qui correspondent à votre projet.',
    color: 'bg-primary-soft text-primary',
  },
  {
    icon: FileText,
    title: 'Préparer votre candidature',
    description: 'Centralisez vos CV et préparez un CV ou un e-mail adapté à l’entreprise visée.',
    color: 'bg-gold-soft text-gold-ink',
  },
  {
    icon: BriefcaseBusiness,
    title: 'Suivre vos démarches',
    description: 'Notez vos candidatures, leurs étapes et les prochaines actions à ne pas oublier.',
    color: 'bg-success-soft text-success',
  },
  {
    icon: BarChart3,
    title: 'Garder une vue d’ensemble',
    description: 'Retrouvez votre activité et l’évolution de votre recherche depuis le tableau de bord.',
    color: 'bg-violet-soft text-violet-ink',
  },
  {
    icon: MapPin,
    title: 'Explorer autour de vous',
    description: 'Parcourez les entreprises sur la carte et gardez vos préférées à portée de main.',
    color: 'bg-primary-soft text-primary',
  },
  {
    icon: GraduationCap,
    title: 'Continuer à progresser',
    description: 'Retrouvez les ressources de formation proposées dans votre espace BookJob.',
    color: 'bg-gold-soft text-gold-ink',
  },
]

const steps = [
  ['01', 'Créez votre espace', 'Connectez-vous pour retrouver un espace candidat personnel.'],
  ['02', 'Explorez les entreprises', 'Recherchez des entreprises et des opportunités qui vous intéressent.'],
  ['03', 'Préparez vos documents', 'Complétez votre profil et organisez vos CV et candidatures.'],
  ['04', 'Suivez votre progression', 'Mettez à jour vos démarches et retrouvez votre recherche au même endroit.'],
]

const footerGroups = [
  {
    title: 'Explorer',
    color: 'text-gold',
    links: [
      ['Entreprises & offres', '/entreprises'],
      ['Carte des entreprises', '/carte'],
      ['Formations', '/formations'],
      ['Mes favoris', '/favoris'],
    ],
  },
  {
    title: 'Votre parcours',
    color: 'text-[#a9cbff]',
    links: [
      ['Mon profil', '/profil'],
      ['CV Studio', '/cv-studio'],
      ['Mes candidatures', '/candidatures'],
      ['Tableau de bord', '/tableau-de-bord'],
    ],
  },
  {
    title: 'Candidatures',
    color: 'text-gold',
    links: [
      ['Rechercher une entreprise', '/rechercher'],
      ['Suivre mes démarches', '/candidatures'],
      ['Préparer mon CV', '/cv-studio'],
      ['Voir mes statistiques', '/statistiques'],
    ],
  },
  {
    title: 'Découvrir',
    color: 'text-[#a9cbff]',
    links: [
      ['Pour qui ?', '#a-propos'],
      ['Comment ça marche', '#fonctionnement'],
      ['Les outils BookJob', '#outils'],
      ['Le projet', '#a-propos'],
    ],
  },
  {
    title: 'Mon espace',
    color: 'text-gold',
    links: [
      ['Se connecter', '/connexion'],
      ['Créer un compte', '/inscription'],
      ['LinkedIn de Houda', 'https://www.linkedin.com/in/houda-b-569aa235b'],
      ['GitHub de Houda', 'https://github.com/HoudaBelgoute'],
    ],
  },
]

function getMarrakechTime(date) {
  const parts = new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'Africa/Casablanca',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  return Object.fromEntries(parts.map(({ type, value }) => [type, Number(value)]))
}

function MarrakechClock() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const { hour, minute, second } = getMarrakechTime(now)
  const hourAngle = ((hour % 12) + minute / 60) * 30
  const minuteAngle = (minute + second / 60) * 6
  const secondAngle = second * 6
  const timeLabel = new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'Africa/Casablanca',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(now)

  return (
    <div
      className="absolute -right-1 -top-12 z-10 flex items-center gap-3 rounded-2xl border border-white/80 bg-card/95 px-3 py-2.5 shadow-pop backdrop-blur sm:-right-4 sm:-top-14"
      role="timer"
      aria-label={`Heure actuelle à Marrakech : ${timeLabel}`}
    >
      <div className="relative h-12 w-12 rounded-full border border-line bg-surface">
        <span className="absolute left-1/2 top-1 h-1 w-1 -translate-x-1/2 rounded-full bg-gold" />
        <span
          className="hero-clock-hand absolute bottom-1/2 left-[calc(50%-1px)] h-[30%] w-[2px] origin-bottom rounded-full bg-navy-900"
          style={{ transform: `rotate(${hourAngle}deg)` }}
        />
        <span
          className="hero-clock-hand absolute bottom-1/2 left-[calc(50%-1px)] h-[39%] w-[2px] origin-bottom rounded-full bg-primary"
          style={{ transform: `rotate(${minuteAngle}deg)` }}
        />
        <span
          className="hero-clock-hand hero-clock-second absolute bottom-1/2 left-[calc(50%-0.5px)] h-[42%] w-px origin-bottom bg-gold"
          style={{ transform: `rotate(${secondAngle}deg)` }}
        />
        <span className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold" />
      </div>
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">Heure de Marrakech</p>
        <p className="mt-0.5 min-w-[4.5rem] font-mono text-sm font-bold tabular-nums text-navy-900">{timeLabel}</p>
      </div>
    </div>
  )
}

export default function LandingPage() {
  return (
    <div className="landing-page min-h-screen bg-surface text-ink">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-surface/95 backdrop-blur">
        <nav className="mx-auto flex max-w-[1280px] items-center justify-between gap-5 px-5 py-4 md:px-8" aria-label="Navigation principale">
          <a href="/" className="flex shrink-0 items-center gap-3" aria-label="BookJob, accueil">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-navy-900 text-gold shadow-card">
              <BriefcaseBusiness size={22} />
            </span>
            <span className="text-[23px] font-bold tracking-tight text-navy-900">
              Book<span className="text-primary">Job</span>
            </span>
          </a>
          <div className="hidden items-center gap-8 text-sm font-medium text-muted md:flex">
            <a className="transition-colors hover:text-primary" href="#fonctionnement">Comment ça marche</a>
            <a className="transition-colors hover:text-primary" href="#outils">Les outils</a>
            <a className="transition-colors hover:text-primary" href="#a-propos">À propos</a>
          </div>
          <Link to="/connexion" className="btn-primary !shrink-0 !whitespace-nowrap !rounded-full !px-3 !py-2.5 text-sm sm:!px-5">
            Mon espace <ArrowRight size={16} />
          </Link>
        </nav>
      </header>

      <main>
        <section className="relative isolate overflow-hidden">
          <img
            src="/bookjob-hero.svg"
            alt=""
            aria-hidden="true"
            className="hero-art pointer-events-none absolute inset-0 -z-10 h-full w-full object-cover object-[62%_center] opacity-70"
          />
          <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-r from-surface via-surface/75 to-surface/10" />
          <div className="pointer-events-none absolute -right-36 -top-40 -z-10 h-[520px] w-[520px] rounded-full bg-primary-soft/50 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-48 left-[-10rem] -z-10 h-[420px] w-[420px] rounded-full bg-gold-soft/70 blur-3xl" />
          <div className="mx-auto grid max-w-[1280px] items-center gap-12 px-5 py-16 md:px-8 md:py-24 lg:grid-cols-[1fr_0.92fr] lg:gap-16 lg:py-28">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-4 py-2 text-sm font-semibold text-primary shadow-card">
                <Sparkles size={16} className="text-gold-ink" />
                Votre recherche, mieux organisée
              </span>
              <h1 className="mt-7 max-w-[700px] text-5xl font-bold leading-[1.06] tracking-[-0.045em] text-navy-900 md:text-6xl lg:text-[70px]">
                Le bon prochain pas commence <span className="text-primary">ici.</span>
              </h1>
              <p className="mt-6 max-w-[590px] text-lg leading-8 text-muted md:text-xl">
                BookJob rassemble les outils essentiels pour chercher des opportunités, préparer vos candidatures et suivre votre parcours professionnel.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link to="/connexion" className="btn-primary !rounded-full !px-6 !py-3.5">
                  Découvrir mon espace <ArrowRight size={17} />
                </Link>
                <a href="#fonctionnement" className="btn-outline !rounded-full !px-6 !py-3.5">
                  Voir comment ça marche
                </a>
              </div>
              <a href="#fonctionnement" className="mt-10 inline-flex items-center gap-2 text-sm font-semibold text-muted transition-colors hover:text-primary">
                Faites défiler pour découvrir BookJob <ArrowDown size={16} />
              </a>
            </div>

            <div className="relative mx-auto w-full max-w-[560px]">
              <MarrakechClock />
              <span aria-hidden="true" className="hero-confetti absolute -left-2 top-[24%] z-10 h-2 w-7 rounded-full bg-gold/80" />
              <span aria-hidden="true" className="hero-confetti absolute -right-3 top-[48%] z-10 h-2 w-8 rounded-full bg-primary/45" />
              <span aria-hidden="true" className="hero-confetti absolute right-[12%] top-[8%] z-10 h-2 w-5 rounded-full bg-success/45" />
              <div className="hero-confetti absolute -left-5 -top-5 h-24 w-24 rounded-[2rem] border border-primary/15" />
              <div className="hero-confetti absolute -bottom-5 -right-5 h-28 w-28 rounded-full border border-gold/40" />
              <div className="hero-card relative rounded-[30px] border border-line bg-card/95 p-4 shadow-pop backdrop-blur-sm sm:p-6">
                <div className="flex items-center justify-between border-b border-line pb-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary">
                      <BriefcaseBusiness size={20} />
                    </span>
                    <div>
                      <p className="text-sm font-bold text-navy-900">Votre espace candidat</p>
                      <p className="mt-0.5 text-xs text-muted">Tout votre parcours au même endroit</p>
                    </div>
                  </div>
                  <span className="rounded-full bg-success-soft px-3 py-1 text-xs font-semibold text-success">BookJob</span>
                </div>
                <div className="mt-5 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl bg-surface p-4">
                    <p className="text-xs font-medium text-muted">Mon profil</p>
                    <p className="mt-2 text-lg font-bold text-navy-900">À compléter</p>
                    <div className="mt-4 h-2 rounded-full bg-line">
                      <div className="h-full w-2/3 rounded-full bg-gold" />
                    </div>
                    <p className="mt-2 text-xs text-muted">Avancez à votre rythme</p>
                  </div>
                  <div className="rounded-2xl bg-navy-900 p-4 text-white">
                    <p className="text-xs font-medium text-white/65">Prochaine étape</p>
                    <p className="mt-2 text-lg font-semibold">Explorer les offres</p>
                    <span className="mt-4 inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-gold">
                      <ArrowRight size={17} />
                    </span>
                  </div>
                </div>
                <div className="mt-4 rounded-2xl border border-line p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold text-navy-900">Mes candidatures</p>
                      <p className="mt-1 text-xs text-muted">Un suivi clair, de l’envoi à la réponse</p>
                    </div>
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gold-soft text-gold-ink">
                      <Bookmark size={18} />
                    </span>
                  </div>
                  <div className="mt-4 space-y-3">
                    {['À préparer', 'Envoyée', 'À relancer'].map((label, index) => (
                      <div key={label} className="flex items-center gap-3">
                        <span className={`flex h-7 w-7 items-center justify-center rounded-full ${index === 1 ? 'bg-success-soft text-success' : 'bg-chip text-muted'}`}>
                          {index === 1 ? <Check size={15} /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}
                        </span>
                        <span className="flex-1 text-sm text-ink">{label}</span>
                        <span className="h-1.5 w-16 rounded-full bg-chip" />
                      </div>
                    ))}
                  </div>
                </div>
                <p className="mt-4 text-center text-xs text-muted">Un aperçu de vos outils de recherche et de suivi</p>
              </div>
            </div>
          </div>
        </section>

        <section id="fonctionnement" className="scroll-mt-24 bg-card py-20 md:py-28">
          <div className="mx-auto max-w-[1280px] px-5 md:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <p className="eyebrow">Comment ça marche</p>
              <h2 className="page-title mt-4 text-4xl md:text-5xl">Une recherche plus simple, étape par étape.</h2>
              <p className="mt-5 text-base leading-7 text-muted">BookJob vous accompagne pour transformer votre recherche en un parcours organisé et facile à suivre.</p>
            </div>
            <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {steps.map(([number, title, description]) => (
                <article key={number} className="rounded-2xl border border-line bg-surface p-6">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-navy-900 text-sm font-bold text-gold">{number}</span>
                  <h3 className="mt-5 text-lg font-bold text-navy-900">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="outils" className="scroll-mt-24 py-20 md:py-28">
          <div className="mx-auto max-w-[1280px] px-5 md:px-8">
            <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
              <div className="max-w-2xl">
                <p className="eyebrow">Les outils BookJob</p>
                <h2 className="page-title mt-4 text-4xl md:text-5xl">Tout ce qu’il faut pour avancer.</h2>
              </div>
              <p className="max-w-md text-base leading-7 text-muted">Des outils pratiques pour organiser vos démarches sans perdre de vue l’essentiel.</p>
            </div>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {tools.map(({ icon: Icon, title, description, color }) => (
                <article key={title} className="rounded-2xl border border-line bg-card p-6 transition-transform hover:-translate-y-1">
                  <span className={`flex h-12 w-12 items-center justify-center rounded-2xl ${color}`}>
                    <Icon size={22} />
                  </span>
                  <h3 className="mt-5 text-lg font-bold text-navy-900">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="a-propos" className="scroll-mt-24 px-5 pb-20 md:px-8 md:pb-28">
          <div className="mx-auto flex max-w-[1280px] flex-col items-start justify-between gap-8 rounded-[30px] bg-navy-900 px-7 py-10 text-white sm:px-10 md:flex-row md:items-center md:px-14 md:py-14">
            <div className="max-w-2xl">
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-gold">À propos du projet</p>
              <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">Un espace pensé pour accompagner votre parcours.</h2>
              <p className="mt-4 max-w-xl leading-7 text-white/70">BookJob est un projet réalisé par Houda Belgoute pour rendre la recherche d’opportunités plus claire et mieux organisée.</p>
            </div>
            <Link to="/connexion" className="inline-flex shrink-0 items-center gap-2 rounded-full bg-gold px-6 py-3.5 font-semibold text-navy-900 transition-transform hover:-translate-y-0.5">
              Entrer dans BookJob <ArrowRight size={17} />
            </Link>
          </div>
        </section>
      </main>

      <footer className="bg-navy-900 text-white">
        <div className="mx-auto max-w-[1280px] px-5 pb-7 pt-12 md:px-8 md:pt-16">
          <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-[1.3fr_repeat(5,minmax(0,1fr))]">
            <div className="max-w-[250px]">
              <a href="/" className="inline-flex items-center gap-3 text-xl font-bold tracking-tight" aria-label="BookJob, accueil">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 text-gold">
                  <BriefcaseBusiness size={21} />
                </span>
                <span>Book<span className="text-[#8fc0ff]">Job</span></span>
              </a>
              <p className="mt-4 text-sm leading-6 text-white/65">
                Les opportunités et les outils pour préparer votre candidature, au même endroit.
              </p>
            </div>
            {footerGroups.map(({ title, color, links }) => (
              <div key={title}>
                <h2 className={`mb-4 text-sm font-bold ${color}`}>{title}</h2>
                <ul className="space-y-3">
                  {links.map(([label, href]) => {
                    const external = href.startsWith('https://')
                    const linkClass = 'text-[13px] leading-5 text-white/75 transition-colors hover:text-white'
                    return (
                      <li key={label}>
                        {external ? (
                          <a href={href} target="_blank" rel="noopener noreferrer" className={linkClass}>{label}</a>
                        ) : href.startsWith('#') ? (
                          <a href={href} className={linkClass}>{label}</a>
                        ) : (
                          <Link to={href} className={linkClass}>{label}</Link>
                        )}
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </div>
          <div className="mt-12 flex flex-col gap-5 border-t border-white/10 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-white/65">© {new Date().getFullYear()} BookJob · Un projet réalisé par Houda Belgoute</p>
            <div className="flex items-center gap-2">
              <a
                href="https://www.linkedin.com/in/houda-b-569aa235b"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn de Houda Belgoute (ouvre un nouvel onglet)"
                className="flex h-10 w-10 items-center justify-center rounded-xl text-white/75 transition-colors hover:bg-white/10 hover:text-white"
              >
                <Linkedin size={19} />
              </a>
              <a
                href="https://github.com/HoudaBelgoute"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub de Houda Belgoute (ouvre un nouvel onglet)"
                className="flex h-10 w-10 items-center justify-center rounded-xl text-white/75 transition-colors hover:bg-white/10 hover:text-white"
              >
                <Github size={19} />
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
