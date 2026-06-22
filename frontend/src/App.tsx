import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import LoadingFallback from './components/LoadingFallback'

// Code splitting: each page is loaded lazily to reduce initial bundle size.
// This means users only download the JavaScript for pages they actually visit,
// improving Time-To-Interactive (TTI) on first load.
const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const WizardsPage = lazy(() => import('./pages/WizardsPage'))
const TemplateWizardPage = lazy(() => import('./pages/TemplateWizardPage'))
const TableBrowserPage = lazy(() => import('./pages/TableBrowserPage'))
const QueryConsolePage = lazy(() => import('./pages/QueryConsolePage'))
const ConfigSyncPage = lazy(() => import('./pages/ConfigSyncPage'))
const UsersPage = lazy(() => import('./pages/UsersPage'))
const ServersPage = lazy(() => import('./pages/ServersPage'))
const ConfigDiffPage = lazy(() => import('./pages/ConfigDiffPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const ClustersPage = lazy(() => import('./pages/ClustersPage'))
const ClusterDetailPage = lazy(() => import('./pages/ClusterDetailPage'))
// MainLayout is NOT lazy-loaded because it's needed immediately after login
import MainLayout from './components/layout/MainLayout'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={
        <Suspense fallback={<LoadingFallback />}>
          <LoginPage />
        </Suspense>
      } />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        {/* Each route wrapped in Suspense for lazy-loaded page chunks */}
        <Route path="dashboard" element={
          <Suspense fallback={<LoadingFallback />}>
            <DashboardPage />
          </Suspense>
        } />
        <Route path="wizards" element={
          <Suspense fallback={<LoadingFallback />}>
            <WizardsPage />
          </Suspense>
        } />
        <Route path="wizards/:wizardId" element={
          <Suspense fallback={<LoadingFallback />}>
            <WizardsPage />
          </Suspense>
        } />
        <Route path="template" element={
          <Suspense fallback={<LoadingFallback />}>
            <TemplateWizardPage />
          </Suspense>
        } />
        <Route path="tables" element={
          <Suspense fallback={<LoadingFallback />}>
            <TableBrowserPage />
          </Suspense>
        } />
        <Route path="tables/:tableName" element={
          <Suspense fallback={<LoadingFallback />}>
            <TableBrowserPage />
          </Suspense>
        } />
        <Route path="query" element={
          <Suspense fallback={<LoadingFallback />}>
            <QueryConsolePage />
          </Suspense>
        } />
        <Route path="sync" element={
          <Suspense fallback={<LoadingFallback />}>
            <ConfigSyncPage />
          </Suspense>
        } />
        <Route path="config-diff" element={
          <Suspense fallback={<LoadingFallback />}>
            <ConfigDiffPage />
          </Suspense>
        } />
        <Route path="users" element={
          <Suspense fallback={<LoadingFallback />}>
            <UsersPage />
          </Suspense>
        } />
        <Route path="servers" element={
          <Suspense fallback={<LoadingFallback />}>
            <ServersPage />
          </Suspense>
        } />
        <Route path="clusters" element={
          <Suspense fallback={<LoadingFallback />}>
            <ClustersPage />
          </Suspense>
        } />
        <Route path="clusters/:clusterId" element={
          <Suspense fallback={<LoadingFallback />}>
            <ClusterDetailPage />
          </Suspense>
        } />
        <Route path="settings" element={
          <Suspense fallback={<LoadingFallback />}>
            <SettingsPage />
          </Suspense>
        } />
      </Route>
    </Routes>
  )
}
