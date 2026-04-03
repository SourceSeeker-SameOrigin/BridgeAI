import { useState } from 'react'
import { Layout } from 'antd'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

const { Content } = Layout

export default function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <Layout style={{ minHeight: '100vh', background: '#0a0e1a' }}>
      <Sidebar onCollapsedChange={setSidebarCollapsed} />
      <Layout style={{ marginLeft: sidebarCollapsed ? 64 : 240, background: '#0a0e1a', transition: 'margin-left 0.2s' }}>
        <TopBar />
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
