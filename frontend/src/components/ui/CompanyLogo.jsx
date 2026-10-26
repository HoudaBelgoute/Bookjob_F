import { useState } from 'react'
import { TONES } from '../../data/data'

const SIZES = {
  sm: 'h-10 w-10 rounded-xl text-[12px]',
  md: 'h-12 w-12 rounded-xl text-[14px]',
  lg: 'h-14 w-14 rounded-2xl text-[16px]',
  xl: 'h-16 w-16 rounded-2xl text-[18px]',
}

// Logo de l'entreprise (icône de son site officiel). Repli sur les initiales si l'image manque ou est trop petite.
export default function CompanyLogo({ company, size = 'md', className = '' }) {
  const [failed, setFailed] = useState(false)
  const tone = TONES[company?.tone] || TONES.blue
  const url = company?.logo_url
  const base = `relative flex shrink-0 items-center justify-center overflow-hidden font-bold ${SIZES[size]} ${className}`

  if (!url || failed) {
    return (
      <div className={base} style={{ background: tone.bg, color: tone.fg }} aria-hidden="true">
        {company?.initials || '?'}
      </div>
    )
  }
  return (
    <div className={`${base} border border-line bg-white p-1.5`} aria-hidden="true">
      <img
        src={url}
        alt=""
        loading="lazy"
        referrerPolicy="no-referrer"
        className="h-full w-full object-contain"
        onError={() => setFailed(true)}
        onLoad={(e) => {
          // Les sites sans icône renvoient une miniature générique de 16 px : on préfère les initiales.
          if (e.currentTarget.naturalWidth < 32) setFailed(true)
        }}
      />
    </div>
  )
}
