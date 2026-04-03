import { lazy, Suspense, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import type { RouteObject } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import useAuthStore from './stores/useAuthStore'

/** Redirect to /login if not authenticated */
function AuthGuard({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

const LoginPage = lazy(() => import('./pages/Login'))
const LandingPage = lazy(() => import('./pages/Landing'))
const DocsPage = lazy(() => import('./pages/Docs'))
const DashboardPage = lazy(() => import('./pages/Dashboard'))
const ChatPage = lazy(() => import('./pages/Chat'))
const AgentsPage = lazy(() => import('./pages/Agents'))
const MCPPage = lazy(() => import('./pages/MCP'))
const KnowledgePage = lazy(() => import('./pages/Knowledge'))
const PluginsPage = lazy(() => import('./pages/Plugins'))
const AuditLogPage = lazy(() => import('./pages/AuditLog'))
const SettingsPage = lazy(() => import('./pages/Settings'))
const WorkflowsPage = lazy(() => import('./pages/Workflows'))

function LazyWrapper({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div
          style={{
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div className="animate-pulse-glow" style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          }} />
        </div>
      }
    >
      {children}
    </Suspense>
  )
}

/** Root index: if logged in go to dashboard, otherwise show landing page */
function RootIndex() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }
  return (
    <LazyWrapper>
      <LandingPage />
    </LazyWrapper>
  )
}

/** Standalone docs wrapper - enables scrolling for the full-page docs layout */
function DocsWrapper() {
  useEffect(() => {
    const root = document.getElementById('root')
    if (root) root.style.overflow = 'auto'
    return () => {
      if (root) root.style.overflow = ''
    }
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: '#0a0e1a', padding: 24 }}>
      <DocsPage />
    </div>
  )
}

const routes: RouteObject[] = [
  // Public pages (no sidebar)
  {
    path: '/',
    index: true,
    element: <RootIndex />,
  },
  {
    path: '/login',
    element: (
      <LazyWrapper>
        <LoginPage />
      </LazyWrapper>
    ),
  },
  {
    path: '/docs',
    element: (
      <LazyWrapper>
        <DocsWrapper />
      </LazyWrapper>
    ),
  },
  // App pages (with sidebar, requires auth)
  {
    element: <AuthGuard><AppLayout /></AuthGuard>,
    children: [
      {
        path: 'dashboard',
        element: <LazyWrapper><DashboardPage /></LazyWrapper>,
      },
      {
        path: 'chat',
        element: <LazyWrapper><ChatPage /></LazyWrapper>,
      },
      {
        path: 'agents',
        element: <LazyWrapper><AgentsPage /></LazyWrapper>,
      },
      {
        path: 'mcp',
        element: <LazyWrapper><MCPPage /></LazyWrapper>,
      },
      {
        path: 'knowledge',
        element: <LazyWrapper><KnowledgePage /></LazyWrapper>,
      },
      {
        path: 'plugins',
        element: <LazyWrapper><PluginsPage /></LazyWrapper>,
      },
      {
        path: 'workflows',
        element: <LazyWrapper><WorkflowsPage /></LazyWrapper>,
      },
      {
        path: 'audit',
        element: <LazyWrapper><AuditLogPage /></LazyWrapper>,
      },
      {
        path: 'settings',
        element: <LazyWrapper><SettingsPage /></LazyWrapper>,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]

export default routes
