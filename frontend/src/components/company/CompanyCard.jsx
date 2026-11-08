import { ArrowRight, Bookmark, Globe, Star } from 'lucide-react'
import { useState } from 'react'
import CompanyLogo from '../ui/CompanyLogo'
import SitePreview from './SitePreview'
import { hostOf } from './siteShot'

export default function CompanyCard({ company: c, favorite, onFavorite, onOpen }) {
  const [hover, setHover] = useState(false)

  return (
    <article
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onOpen}
      className="card group flex cursor-pointer flex-col overflow-hidden transition duration-300 hover:-translate-y-1 hover:border-primary hover:shadow-pop"
    >
      <div className="relative">
        <SitePreview
          url={c.site_web}
          height={190}
          active={hover}
          className="border-b border-line"
          fallback={
            <div className="flex h-full items-center justify-center bg-primary-soft">
              <CompanyLogo company={c} size="xl" />
            </div>
          }
        />
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onFavorite()
          }}
          aria-label={favorite ? 'Retirer des favoris' : 'Suivre l’entreprise'}
          className="absolute right-3 top-3 rounded-lg bg-card p-2 text-primary shadow-card transition hover:scale-110"
        >
          <Bookmark size={18} fill={favorite ? 'currentColor' : 'none'} />
        </button>
        {c.site_web && (
          <span className="absolute bottom-3 left-3 flex max-w-[80%] items-center gap-1.5 rounded-full bg-card px-3 py-1 text-[11px] text-muted shadow-card">
            <Globe size={12} className="shrink-0" />
            <span className="truncate">{hostOf(c.site_web)}</span>
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start gap-3">
          <CompanyLogo company={c} size="sm" />
          <div className="min-w-0 flex-1">
            <h2 className="line-clamp-2 text-[18px] font-medium leading-snug text-ink">{c.short}</h2>
            <p className="mt-0.5 truncate text-[13px] text-primary">
              {c.secteur} · {c.quartier}
            </p>
          </div>
          {c.note != null && (
            <span className="shrink-0 text-[13px] font-semibold text-ink">
              {c.note}
              <span className="font-normal text-faint">/5</span>
            </span>
          )}
        </div>

        <p className="mt-3 flex items-center gap-1.5 text-[13px] text-muted">
          <Star size={14} /> {c.note != null ? `${c.nb_avis ?? 0} avis` : 'Non noté'} · {c.site_web ? 'Site web' : 'Sans site web'}
        </p>

        <div className="mt-auto flex items-center justify-between border-t border-line pt-4">
          <span className="text-[12px] text-muted">
            Score <strong className="text-ink">{c.score}</strong> · Priorité {c.priorite}
          </span>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onOpen()
            }}
            className="flex items-center gap-2 text-[15px] font-semibold text-primary"
          >
            Voir l’entreprise
            <ArrowRight size={17} className="transition-transform duration-300 group-hover:translate-x-1.5" />
          </button>
        </div>
      </div>
    </article>
  )
}
