import { TONES } from '../../data/data'

const SIZES = {
  sm: 'h-10 w-10 rounded-xl text-[12px]',
  md: 'h-12 w-12 rounded-xl text-[14px]',
  lg: 'h-14 w-14 rounded-2xl text-[16px]',
  xl: 'h-[58px] w-[58px] rounded-2xl text-[17px]',
}

export default function Avatar({ initials, tone = 'blue', size = 'md' }) {
  const t = TONES[tone] || TONES.blue
  return (
    <div
      className={`flex shrink-0 items-center justify-center font-bold ${SIZES[size]}`}
      style={{ background: t.bg, color: t.fg }}
      aria-hidden="true"
    >
      {initials}
    </div>
  )
}
