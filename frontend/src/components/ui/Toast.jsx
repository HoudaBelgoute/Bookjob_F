import { Check } from 'lucide-react'
import { useStore } from '../../store/useStore'

export default function Toast() {
  const toast = useStore((s) => s.toast)
  if (!toast) return null
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-24 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-xl bg-navy-900 px-4 py-3 text-[14px] font-medium text-white shadow-pop"
    >
      <Check size={16} className="text-gold" />
      {toast.message}
    </div>
  )
}
