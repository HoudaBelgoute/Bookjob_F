import { X } from 'lucide-react'
import { useEffect } from 'react'

export default function Modal({ title, onClose, children, wide = false }) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto overscroll-contain bg-navy-900/50 p-2 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`my-auto max-h-[calc(100dvh-1rem)] w-full overflow-y-auto overscroll-contain ${wide ? 'max-w-2xl' : 'max-w-md'} rounded-2xl bg-white p-4 shadow-pop sm:max-h-[calc(100dvh-2rem)] sm:p-6`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[20px] font-medium">{title}</h2>
          <button onClick={onClose} aria-label="Fermer" className="rounded-lg p-1.5 text-muted hover:bg-surface">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
