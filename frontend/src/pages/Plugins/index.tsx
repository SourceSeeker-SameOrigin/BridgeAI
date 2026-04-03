import { useState, useEffect, useCallback } from 'react'
import { Row, Col, Button, Tag, Spin, message, Tabs, Collapse, Modal, Select, Input } from 'antd'
import {
  AppstoreOutlined,
  DownloadOutlined,
  DeleteOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  ToolOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import GlassCard from '../../components/GlassCard'
import {
  getMarketplacePlugins,
  getInstalledPlugins,
  installPlugin,
  uninstallPlugin,
  executePlugin,
} from '../../api/plugins'
import type { PluginMetadata, InstalledPlugin } from '../../api/plugins'

const CATEGORY_COLORS: Record<string, string> = {
  tool: '#6366f1',
  integration: '#0ea5e9',
  analytics: '#f59e0b',
  security: '#ef4444',
}

export default function PluginsPage() {
  const { t } = useTranslation()
  const [marketplace, setMarketplace] = useState<PluginMetadata[]>([])
  const [installed, setInstalled] = useState<InstalledPlugin[]>([])
  const [loading, setLoading] = useState(false)
  const [installingSet, setInstallingSet] = useState<Set<string>>(new Set())
  const [testModalOpen, setTestModalOpen] = useState(false)
  const [testPlugin, setTestPlugin] = useState<InstalledPlugin | null>(null)
  const [testToolName, setTestToolName] = useState('')
  const [testArgs, setTestArgs] = useState('{}')
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testRunning, setTestRunning] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [mp, inst] = await Promise.all([
        getMarketplacePlugins(),
        getInstalledPlugins(),
      ])
      setMarketplace(mp)
      setInstalled(inst)
    } catch (err) {
      message.error(`${t('plugins.loadFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadData()
  }, [loadData])

  const installedNames = new Set(installed.map((p) => p.plugin_name))

  const handleInstall = async (pluginName: string) => {
    setInstallingSet((prev) => new Set(prev).add(pluginName))
    try {
      await installPlugin(pluginName)
      message.success(t('plugins.installSuccess', { name: pluginName }))
      await loadData()
    } catch (err) {
      message.error(`${t('plugins.installFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    } finally {
      setInstallingSet((prev) => {
        const next = new Set(prev)
        next.delete(pluginName)
        return next
      })
    }
  }

  const handleUninstall = async (pluginId: string, pluginName: string) => {
    try {
      await uninstallPlugin(pluginId)
      message.success(t('plugins.uninstallSuccess', { name: pluginName }))
      await loadData()
    } catch (err) {
      message.error(`${t('plugins.uninstallFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    }
  }

  const openTestModal = (plugin: InstalledPlugin) => {
    setTestPlugin(plugin)
    setTestToolName('')
    setTestArgs('{}')
    setTestResult(null)
    setTestModalOpen(true)
  }

  const handleTestExecute = async () => {
    if (!testPlugin || !testToolName) {
      message.warning(t('plugins.selectToolRequired'))
      return
    }
    let parsedArgs: Record<string, unknown>
    try {
      parsedArgs = JSON.parse(testArgs)
    } catch {
      message.error(t('plugins.invalidJson'))
      return
    }
    setTestRunning(true)
    setTestResult(null)
    try {
      const result = await executePlugin(testPlugin.plugin_name, {
        tool_name: testToolName,
        arguments: parsedArgs,
      })
      setTestResult(JSON.stringify(result, null, 2))
    } catch (err) {
      setTestResult(`${t('plugins.executeFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    } finally {
      setTestRunning(false)
    }
  }

  if (loading) {
    return (
      <div className="animate-fade-in" style={{ textAlign: 'center', padding: 80 }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 32, color: '#6366f1' }} />} />
        <div style={{ color: '#94a3b8', marginTop: 16 }}>{t('plugins.loadingPlugins')}</div>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      <h2 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', marginBottom: 24 }}>
        {t('plugins.title')}
      </h2>

      <Tabs
        defaultActiveKey="marketplace"
        items={[
          {
            key: 'marketplace',
            label: (
              <span>
                <AppstoreOutlined style={{ marginRight: 8 }} />
                {t('plugins.availablePlugins')} ({marketplace.length})
              </span>
            ),
            children: (
              <Row gutter={[16, 16]}>
                {marketplace.map((plugin) => {
                  const isInstalled = installedNames.has(plugin.name)
                  const isInstalling = installingSet.has(plugin.name)
                  return (
                    <Col xs={24} sm={12} lg={8} xl={6} key={plugin.name}>
                      <GlassCard hoverable={false}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                          <div
                            style={{
                              width: 44,
                              height: 44,
                              borderRadius: 10,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              background: `${CATEGORY_COLORS[plugin.category] || '#6366f1'}20`,
                              color: CATEGORY_COLORS[plugin.category] || '#6366f1',
                              fontSize: 20,
                            }}
                          >
                            <AppstoreOutlined />
                          </div>
                          <Tag
                            style={{
                              borderRadius: 4,
                              background: `${CATEGORY_COLORS[plugin.category] || '#6366f1'}15`,
                              borderColor: `${CATEGORY_COLORS[plugin.category] || '#6366f1'}40`,
                              color: CATEGORY_COLORS[plugin.category] || '#6366f1',
                            }}
                          >
                            {plugin.category}
                          </Tag>
                        </div>

                        <h3 style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                          {plugin.display_name}
                        </h3>
                        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>
                          v{plugin.version}
                        </div>
                        <p
                          style={{
                            fontSize: 13,
                            color: '#94a3b8',
                            marginBottom: 12,
                            lineHeight: 1.5,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            minHeight: 40,
                          }}
                        >
                          {plugin.description}
                        </p>

                        <div style={{ fontSize: 12, color: '#64748b', marginBottom: 12 }}>
                          <ToolOutlined style={{ marginRight: 4 }} />
                          {t('plugins.toolCount', { count: plugin.tools.length })}
                        </div>

                        <div style={{ borderTop: '1px solid rgba(148,163,184,0.1)', paddingTop: 12 }}>
                          {isInstalled ? (
                            <Button
                              type="default"
                              size="small"
                              icon={<CheckCircleOutlined />}
                              disabled
                              style={{ color: '#22c55e', borderColor: '#22c55e40' }}
                            >
                              {t('plugins.installed')}
                            </Button>
                          ) : (
                            <Button
                              type="primary"
                              size="small"
                              icon={<DownloadOutlined />}
                              loading={isInstalling}
                              onClick={() => handleInstall(plugin.name)}
                            >
                              {t('common.install')}
                            </Button>
                          )}
                        </div>
                      </GlassCard>
                    </Col>
                  )
                })}
                {marketplace.length === 0 && (
                  <Col span={24}>
                    <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
                      {t('plugins.noAvailablePlugins')}
                    </div>
                  </Col>
                )}
              </Row>
            ),
          },
          {
            key: 'installed',
            label: (
              <span>
                <CheckCircleOutlined style={{ marginRight: 8 }} />
                {t('plugins.installed')} ({installed.length})
              </span>
            ),
            children: (
              <Row gutter={[16, 16]}>
                {installed.map((plugin) => {
                  const meta = marketplace.find((m) => m.name === plugin.plugin_name)
                  return (
                    <Col xs={24} sm={12} lg={8} key={plugin.id}>
                      <GlassCard hoverable={false}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                          <h3 style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', margin: 0 }}>
                            {meta?.display_name || plugin.plugin_name}
                          </h3>
                          <Tag color="success" style={{ borderRadius: 4 }}>
                            v{plugin.plugin_version}
                          </Tag>
                        </div>

                        <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>
                          {plugin.description || meta?.description || t('common.noDescription')}
                        </p>

                        {meta && meta.tools.length > 0 && (
                          <Collapse
                            ghost
                            size="small"
                            items={[
                              {
                                key: '1',
                                label: (
                                  <span style={{ color: '#94a3b8', fontSize: 12 }}>
                                    <ToolOutlined style={{ marginRight: 4 }} />
                                    {t('plugins.toolCount', { count: meta.tools.length })}
                                  </span>
                                ),
                                children: (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {meta.tools.map((tool) => (
                                      <div key={tool.name}>
                                        <div style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 500 }}>
                                          {tool.name}
                                        </div>
                                        <div style={{ fontSize: 12, color: '#64748b' }}>
                                          {tool.description}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ),
                              },
                            ]}
                          />
                        )}

                        <div style={{ borderTop: '1px solid rgba(148,163,184,0.1)', paddingTop: 12, marginTop: 8, display: 'flex', gap: 8 }}>
                          <Button
                            type="text"
                            size="small"
                            icon={<PlayCircleOutlined />}
                            onClick={() => openTestModal(plugin)}
                            style={{ color: '#6366f1', fontSize: 12 }}
                          >
                            {t('common.test')}
                          </Button>
                          <Button
                            type="text"
                            size="small"
                            icon={<DeleteOutlined />}
                            danger
                            onClick={() => handleUninstall(plugin.id, plugin.plugin_name)}
                          >
                            {t('common.uninstall')}
                          </Button>
                        </div>
                      </GlassCard>
                    </Col>
                  )
                })}
                {installed.length === 0 && (
                  <Col span={24}>
                    <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
                      {t('plugins.noInstalledPlugins')}
                    </div>
                  </Col>
                )}
              </Row>
            ),
          },
        ]}
      />

      {/* Test Execution Modal */}
      <Modal
        title={t('plugins.testTitle', { name: testPlugin?.plugin_name || '' })}
        open={testModalOpen}
        onCancel={() => { setTestModalOpen(false); setTestPlugin(null); setTestResult(null) }}
        footer={null}
        width={560}
      >
        {testPlugin && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12 }}>
            <div>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 6 }}>{t('plugins.selectTool')}</div>
              <Select
                value={testToolName || undefined}
                onChange={setTestToolName}
                placeholder={t('plugins.selectToolPlaceholder')}
                style={{ width: '100%' }}
                options={
                  (marketplace.find((m) => m.name === testPlugin.plugin_name)?.tools || []).map(
                    (t) => ({ label: `${t.name} - ${t.description}`, value: t.name }),
                  )
                }
              />
            </div>
            <div>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 6 }}>{t('plugins.params')}</div>
              <Input.TextArea
                rows={4}
                value={testArgs}
                onChange={(e) => setTestArgs(e.target.value)}
                placeholder='{"key": "value"}'
                style={{ fontFamily: 'monospace', fontSize: 13 }}
              />
            </div>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={testRunning}
              onClick={handleTestExecute}
            >
              {t('common.execute')}
            </Button>
            {testResult !== null && (
              <div
                style={{
                  padding: 12,
                  borderRadius: 8,
                  background: 'rgba(0,0,0,0.2)',
                  border: '1px solid rgba(148,163,184,0.15)',
                  maxHeight: 300,
                  overflow: 'auto',
                }}
              >
                <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>{t('plugins.executeResult')}</div>
                <pre style={{ fontSize: 12, color: '#e2e8f0', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {testResult}
                </pre>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
