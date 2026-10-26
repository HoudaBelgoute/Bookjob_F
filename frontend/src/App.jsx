import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AuthGate from './components/AuthGate'
import Layout from './components/layout/Layout'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const Applications = lazy(() => import('./pages/Applications'))
const Favorites = lazy(() => import('./pages/Favorites'))
const Companies = lazy(() => import('./pages/Companies'))
const CvStudio = lazy(() => import('./pages/CvStudio'))
const MapPage = lazy(() => import('./pages/MapPage'))
const Profile = lazy(() => import('./pages/Profile'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const Statistics = lazy(() => import('./pages/Statistics'))
const NotFound = lazy(() => import('./pages/NotFound'))
const Formations = lazy(() => import('./pages/Formations'))

export default function App() {
  return (
    <AuthGate>
      <Suspense fallback={<div className="p-10 text-muted">Chargement…</div>}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="rechercher" element={<SearchPage />} />
            <Route path="candidatures" element={<Applications />} />
            <Route path="favoris" element={<Favorites />} />
            <Route path="entreprises" element={<Companies />} />
            <Route path="carte" element={<MapPage />} />
            <Route path="cv-studio" element={<CvStudio />} />
            <Route path="assistant" element={<Navigate to="/" replace />} />
            <Route path="profil" element={<Profile />} />
            <Route path="parametres" element={<SettingsPage />} />
            <Route path="statistiques" element={<Statistics />} />
            <Route path="formations" element={<Formations />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </AuthGate>
  )
}
