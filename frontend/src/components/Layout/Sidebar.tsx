import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Progress } from 'antd'
import {
  MessageOutlined,
  DashboardOutlined,
  RobotOutlined,
  ApiOutlined,
  BookOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ThunderboltOutlined,
  AppstoreOutlined,
  FileSearchOutlined,
  BranchesOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { getPlan } from '../../api/billing'
import type { PlanInfo } from '../../api/billing'

const { Sider } = Layout

interface SidebarProps {
  onCollapsedChange?: (collapsed: boolean) => void
  mobileOpen?: boolean
  onMobileClose?: () => void
}

export default function Sidebar({ onCollapsedChange, mobileOpen }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [planInfo, setPlanInfo] = useState<PlanInfo | null>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()

  const menuItems = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: t('sidebar.dashboard') },
    { key: '/chat', icon: <MessageOutlined />, label: t('sidebar.chat') },
    { key: '/agents', icon: <RobotOutlined />, label: t('sidebar.agents') },
    { key: '/mcp', icon: <ApiOutlined />, label: t('sidebar.mcp') },
    { key: '/knowledge', icon: <BookOutlined />, label: t('sidebar.knowledge') },
    { key: '/plugins', icon: <AppstoreOutlined />, label: t('sidebar.plugins') },
    { key: '/workflows', icon: <BranchesOutlined />, label: t('sidebar.workflows') },
    { key: '/audit', icon: <FileSearchOutlined />, label: t('sidebar.audit') },
    { key: '/settings', icon: <SettingOutlined />, label: t('sidebar.settings') },
  ]

  // Load real usage data
  useEffect(() => {
    getPlan()
      .then(setPlanInfo)
      .catch(() => { /* silently ignore */ })
  }, [])

  const currentKey = '/' + location.pathname.split('/')[1]

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      trigger={null}
      width={240}
      collapsedWidth={72}
      className={`app-sidebar${mobileOpen ? ' mobile-open' : ''}`}
      style={{
        background: '#111827',
        borderRight: '1px solid rgba(148,163,184,0.1)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        zIndex: 100,
      }}
    >
      {/* Logo Area */}
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          padding: collapsed ? 0 : '0 20px',
          borderBottom: '1px solid rgba(148,163,184,0.1)',
        }}
      >
        <ThunderboltOutlined
          style={{ fontSize: 24, color: '#6366f1' }}
        />
        {!collapsed && (
          <span
            style={{
              marginLeft: 10,
              fontSize: 18,
              fontWeight: 700,
              letterSpacing: -0.5,
            }}
            className="brand-gradient-text"
          >
            BridgeAI
          </span>
        )}
      </div>

      {/* Navigation Menu */}
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[currentKey]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        style={{
          flex: 1,
          borderRight: 'none',
          marginTop: 8,
        }}
      />

      {/* Usage Bar */}
      {!collapsed && planInfo && (
        <div
          style={{
            padding: '16px 20px',
            borderTop: '1px solid rgba(148,163,184,0.1)',
          }}
        >
          <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>
            {t('dashboard.monthlyUsage')}
          </div>
          <Progress
            percent={
              planInfo.monthly_calls_limit > 0
                ? Math.round((planInfo.monthly_calls_used / planInfo.monthly_calls_limit) * 100)
                : 0
            }
            strokeColor={{
              from: '#6366f1',
              to: '#8b5cf6',
            }}
            trailColor="rgba(148,163,184,0.1)"
            size="small"
            format={(p) => `${p}%`}
          />
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
            {planInfo.monthly_calls_used.toLocaleString()} / {planInfo.monthly_calls_limit.toLocaleString()} {t('dashboard.calls')}
          </div>
        </div>
      )}

      {/* Collapse Toggle */}
      <div
        onClick={() => {
          const next = !collapsed
          setCollapsed(next)
          onCollapsedChange?.(next)
        }}
        style={{
          height: 48,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          borderTop: '1px solid rgba(148,163,184,0.1)',
          color: '#94a3b8',
          transition: 'color 0.2s',
        }}
      >
        {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
      </div>
    </Sider>
  )
}
