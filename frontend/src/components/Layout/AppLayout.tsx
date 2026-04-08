import { useState, useCallback } from 'react'
import { Layout } from 'antd'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

const { Content } = Layout

export default function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleMobileMenuToggle = useCallback(() => {
    setMobileOpen((prev) => !prev)
  }, [])

  const handleMobileClose = useCallback(() => {
    setMobileOpen(false)
  }, [])

  return (
    <Layout style={{ minHeight: '100vh', background: '#0a0e1a' }}>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="mobile-overlay" style={{ display: 'none' }} onClick={handleMobileClose} />
      )}
      <Sidebar
        onCollapsedChange={setSidebarCollapsed}
        mobileOpen={mobileOpen}
        onMobileClose={handleMobileClose}
      />
      <Layout
        className="app-content"
        style={{
          marginLeft: sidebarCollapsed ? 72 : 240,
          background: '#0a0e1a',
          transition: 'margin-left 0.2s',
        }}
      >
        <TopBar onMobileMenuToggle={handleMobileMenuToggle} />
        <Content
          style={{
            height: 'calc(100vh - 64px)',
            overflow: 'auto',
            padding: 24,
            background: '#0a0e1a',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
