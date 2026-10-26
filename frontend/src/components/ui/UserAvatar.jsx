import { useEffect, useState } from 'react'
import { initialsOf } from '../../data/data'

// Photo de l'utilisateur, ou ses initiales tant qu'il n'en a pas importé.
export default function UserAvatar({ name, url, className = 'h-10 w-10 rounded-full text-[13px]' }) {
  const [broken, setBroken] = useState(false)
  useEffect(() => setBroken(false), [url])
  return (
    <span className={`flex shrink-0 items-center justify-center overflow-hidden bg-[#dbe6f7] font-bold text-navy-900 ${className}`}>
      {url && !broken ? (
        <img src={url} alt="" className="h-full w-full object-cover" onError={() => setBroken(true)} />
      ) : (
        initialsOf(name)
      )}
    </span>
  )
}
