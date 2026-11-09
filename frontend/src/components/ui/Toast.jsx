import { CircleAlert, Check } from 'lucide-react'
import { useStore } from '../../store/useStore'

export default function Toast() {
  const toast = useStore((s) => s.toast)
  if (!toast) return null
  const isError = toast.type === 'error'
  return (
    <div
      role={isError ? 'alert' : 'status'}
      aria-live="polite"
      className={`fixed bottom-24 left-1/2 z-50 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-2 rounded-xl px-4 py-3 text-[14px] font-medium text-white shadow-pop ${isError ? 'bg-red-700' : 'bg-navy-900'}`}
    >
      {isError ? <CircleAlert size={16} className="shrink-0" /> : <Check size={16} className="shrink-0 text-gold" />}
      {toast.message}
    </div>
  )
}
