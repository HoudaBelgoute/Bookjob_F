import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="mx-auto max-w-[600px] px-4 py-24 text-center">
      <p className="eyebrow">Erreur 404</p>
      <h1 className="page-title mt-3">Page introuvable</h1>
      <p className="mt-3 text-muted">La page que vous cherchez n’existe pas ou a été déplacée.</p>
      <Link to="/" className="btn-primary mt-6">
        Retour au tableau de bord
      </Link>
    </div>
  )
}
