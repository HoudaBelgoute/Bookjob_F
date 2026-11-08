import { useState } from 'react'
import { siteShot } from './siteShot'

export default function SitePreview({ url, height = 190, active, fallback = null, className = '' }) {
  const [hover, setHover] = useState(false)
  const [failed, setFailed] = useState(false)
  const src = failed ? null : siteShot(url)
  const on = active ?? hover

  return (
    <div
      className={`relative overflow-hidden bg-chip ${className}`}
      style={{ height }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {src ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
          className="absolute left-0 top-0 w-full select-none"
          style={{
            transform: on ? `translateY(min(0px, calc(-100% + ${height}px)))` : 'translateY(0)',
            transition: on ? 'transform 6s ease-in-out' : 'transform 0.6s ease',
          }}
          draggable={false}
        />
      ) : (
        fallback
      )}
    </div>
  )
}
