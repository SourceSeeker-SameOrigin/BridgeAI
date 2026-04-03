import { useState, useCallback, useEffect, useRef } from 'react'
import {
  Input,
  Badge,
  Avatar,
  Dropdown,
  Drawer,
  List,
  Button,
  Tag,
  Empty,
  Spin,
  message,
} from 'antd'
import {
  SearchOutlined,
  BellOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
  CheckOutlined,
  RobotOutlined,
  BookOutlined,
  MessageOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useDebounceFn } from 'ahooks'
import { useTranslation } from 'react-i18next'
import useAuthStore from '../../stores/useAuthStore'
import { useNavigate } from 'react-router-dom'
import { globalSearch } from '../../api/search'
import type { SearchResults } from '../../api/search'
import {
  getNotifications,
  getUnreadCount,
  markAsRead,
  markAllAsRead,
} from '../../api/notifications'
import type { NotificationItem } from '../../api/notifications'

export default function TopBar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const { t } = useTranslation()

  // --- Search State ---
  const [searchValue, setSearchValue] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResults | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)

  // --- Notification State ---
  const [notifDrawerOpen, setNotifDrawerOpen] = useState(false)
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifLoading, setNotifLoading] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // --- Search Logic ---
  const { run: debouncedSearch } = useDebounceFn(
    async (value: string) => {
      if (!value.trim()) {
        setSearchResults(null)
        setSearchOpen(false)
        return
      }
      setSearchLoading(true)
      try {
        const results = await globalSearch(value.trim())
        setSearchResults(results)
        const hasResults =
          results.agents.length > 0 ||
          results.knowledge_bases.length > 0 ||
          results.conversations.length > 0
        setSearchOpen(hasResults)
      } catch {
        setSearchResults(null)
        setSearchOpen(false)
      } finally {
        setSearchLoading(false)
      }
    },
    { wait: 300 },
  )

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value
      setSearchValue(val)
      debouncedSearch(val)
    },
    [debouncedSearch],
  )

  const handleSearchResultClick = useCallback(
    (type: string, id: string) => {
      if (type === 'agent') {
        navigate(`/chat?agentId=${id}`)
      } else if (type === 'knowledge_base') {
        navigate('/knowledge')
      } else if (type === 'conversation') {
        navigate('/chat')
      }
      setSearchOpen(false)
      setSearchValue('')
      setSearchResults(null)
    },
    [navigate],
  )

  // Close search dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // --- Notification Logic ---
  const loadUnreadCount = useCallback(async () => {
    try {
      const count = await getUnreadCount()
      setUnreadCount(count)
    } catch {
      // silently ignore
    }
  }, [])

  // Poll unread count every 30 seconds
  useEffect(() => {
    loadUnreadCount()
    const interval = setInterval(loadUnreadCount, 30_000)
    return () => clearInterval(interval)
  }, [loadUnreadCount])

  const handleOpenNotifications = useCallback(async () => {
    setNotifDrawerOpen(true)
    setNotifLoading(true)
    try {
      const data = await getNotifications(1, 50)
      setNotifications(data.items)
      setUnreadCount(data.unreadCount)
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : '加载失败'
      message.error(`加载通知失败: ${errorMsg}`)
    } finally {
      setNotifLoading(false)
    }
  }, [])

  const handleMarkRead = useCallback(
    async (id: string) => {
      try {
        await markAsRead(id)
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, isRead: true } : n)),
        )
        setUnreadCount((prev) => Math.max(0, prev - 1))
      } catch {
        message.error('操作失败')
      }
    },
    [],
  )

  const handleMarkAllRead = useCallback(async () => {
    try {
      await markAllAsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })))
      setUnreadCount(0)
    } catch {
      message.error('操作失败')
    }
  }, [])

  const getNotifTagColor = (type: string): string => {
    switch (type) {
      case 'success':
        return 'success'
      case 'warning':
        return 'warning'
      case 'error':
        return 'error'
      default:
        return 'processing'
    }
  }

  const getNotifTypeLabel = (type: string): string => {
    switch (type) {
      case 'success':
        return '成功'
      case 'warning':
        return '警告'
      case 'error':
        return '错误'
      default:
        return '信息'
    }
  }

  const formatTime = (iso: string): string => {
    if (!iso) return ''
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour} 小时前`
    const diffDay = Math.floor(diffHour / 24)
    if (diffDay < 7) return `${diffDay} 天前`
    return d.toLocaleDateString('zh-CN')
  }

  const hasSearchResults =
    searchResults &&
    (searchResults.agents.length > 0 ||
      searchResults.knowledge_bases.length > 0 ||
      searchResults.conversations.length > 0)

  return (
    <div
      style={{
        height: 64,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        background: 'rgba(17,24,39,0.8)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(148,163,184,0.1)',
      }}
    >
      {/* Search */}
      <div ref={searchRef} style={{ position: 'relative' }}>
        <Input
          prefix={
            searchLoading ? (
              <Spin
                indicator={<LoadingOutlined style={{ fontSize: 14, color: '#6366f1' }} />}
              />
            ) : (
              <SearchOutlined style={{ color: '#64748b' }} />
            )
          }
          placeholder={t('topbar.searchPlaceholder')}
          value={searchValue}
          onChange={handleSearchChange}
          onFocus={() => {
            if (searchResults) setSearchOpen(true)
          }}
          allowClear
          style={{
            width: 320,
            background: 'rgba(26,35,50,0.8)',
            borderColor: 'rgba(148,163,184,0.1)',
            borderRadius: 8,
          }}
        />
        {searchOpen && hasSearchResults && (
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: 4,
              background: '#1a2332',
              border: '1px solid rgba(148,163,184,0.15)',
              borderRadius: 8,
              maxHeight: 400,
              overflow: 'auto',
              zIndex: 1000,
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            }}
          >
            {searchResults!.agents.length > 0 && (
              <>
                <div style={{ padding: '8px 16px', fontSize: 12, color: '#94a3b8' }}>
                  <RobotOutlined style={{ marginRight: 4 }} />
                  {t('topbar.searchGroupAgents')}
                </div>
                {searchResults!.agents.map((a) => (
                  <div
                    key={`agent-${a.id}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => handleSearchResultClick('agent', a.id)}
                    style={{
                      padding: '8px 16px 8px 28px',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(99,102,241,0.1)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent'
                    }}
                  >
                    <div style={{ fontWeight: 500, color: '#e2e8f0' }}>{a.name}</div>
                    {a.description && (
                      <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                        {a.description.slice(0, 50)}
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}
            {searchResults!.knowledge_bases.length > 0 && (
              <>
                <div style={{ padding: '8px 16px', fontSize: 12, color: '#94a3b8' }}>
                  <BookOutlined style={{ marginRight: 4 }} />
                  {t('topbar.searchGroupKnowledge')}
                </div>
                {searchResults!.knowledge_bases.map((kb) => (
                  <div
                    key={`kb-${kb.id}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => handleSearchResultClick('knowledge_base', kb.id)}
                    style={{
                      padding: '8px 16px 8px 28px',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(99,102,241,0.1)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent'
                    }}
                  >
                    <div style={{ fontWeight: 500, color: '#e2e8f0' }}>{kb.name}</div>
                    {kb.description && (
                      <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                        {kb.description.slice(0, 50)}
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}
            {searchResults!.conversations.length > 0 && (
              <>
                <div style={{ padding: '8px 16px', fontSize: 12, color: '#94a3b8' }}>
                  <MessageOutlined style={{ marginRight: 4 }} />
                  {t('topbar.searchGroupConversations')}
                </div>
                {searchResults!.conversations.map((c) => (
                  <div
                    key={`conv-${c.id}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => handleSearchResultClick('conversation', c.id)}
                    style={{
                      padding: '8px 16px 8px 28px',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(99,102,241,0.1)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent'
                    }}
                  >
                    <div style={{ fontWeight: 500, color: '#e2e8f0' }}>
                      {c.title || t('topbar.newConversation')}
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* Right Section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        {/* Notifications */}
        <Badge count={unreadCount} size="small">
          <BellOutlined
            onClick={handleOpenNotifications}
            style={{ fontSize: 18, color: '#94a3b8', cursor: 'pointer' }}
          />
        </Badge>

        {/* User */}
        <Dropdown
          menu={{
            items: [
              {
                key: 'settings',
                icon: <SettingOutlined />,
                label: t('topbar.settings'),
                onClick: () => navigate('/settings'),
              },
              { type: 'divider' },
              {
                key: 'logout',
                icon: <LogoutOutlined />,
                label: t('topbar.logout'),
                onClick: handleLogout,
              },
            ],
          }}
          placement="bottomRight"
          trigger={['click']}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: 8,
              transition: 'background 0.2s',
            }}
          >
            <Avatar
              size={32}
              icon={<UserOutlined />}
              style={{
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              }}
            />
            <span style={{ color: '#e2e8f0', fontSize: 14 }}>
              {user?.username || t('topbar.user')}
            </span>
          </div>
        </Dropdown>
      </div>

      {/* Notification Drawer */}
      <Drawer
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>通知</span>
            {unreadCount > 0 && (
              <Button
                type="link"
                size="small"
                icon={<CheckOutlined />}
                onClick={handleMarkAllRead}
              >
                全部已读
              </Button>
            )}
          </div>
        }
        open={notifDrawerOpen}
        onClose={() => setNotifDrawerOpen(false)}
        width={400}
        styles={{
          body: { padding: 0 },
          header: { borderBottom: '1px solid rgba(148,163,184,0.1)' },
        }}
      >
        {notifLoading ? (
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              padding: 40,
            }}
          >
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} />} />
          </div>
        ) : notifications.length === 0 ? (
          <Empty
            description="暂无通知"
            style={{ marginTop: 60 }}
          />
        ) : (
          <List
            dataSource={notifications}
            renderItem={(item) => (
              <List.Item
                style={{
                  padding: '12px 16px',
                  background: item.isRead
                    ? 'transparent'
                    : 'rgba(99,102,241,0.05)',
                  cursor: item.isRead ? 'default' : 'pointer',
                  borderBottom: '1px solid rgba(148,163,184,0.08)',
                }}
                onClick={() => {
                  if (!item.isRead) handleMarkRead(item.id)
                }}
              >
                <List.Item.Meta
                  title={
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                      }}
                    >
                      {!item.isRead && (
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            background: '#6366f1',
                            flexShrink: 0,
                          }}
                        />
                      )}
                      <span style={{ fontSize: 14 }}>{item.title}</span>
                      <Tag
                        color={getNotifTagColor(item.type)}
                        style={{ fontSize: 11, marginLeft: 'auto' }}
                      >
                        {getNotifTypeLabel(item.type)}
                      </Tag>
                    </div>
                  }
                  description={
                    <div>
                      {item.content && (
                        <div
                          style={{
                            fontSize: 13,
                            color: '#8c8c8c',
                            marginBottom: 4,
                          }}
                        >
                          {item.content}
                        </div>
                      )}
                      <div style={{ fontSize: 12, color: '#bfbfbf' }}>
                        {formatTime(item.createdAt)}
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Drawer>
    </div>
  )
}
