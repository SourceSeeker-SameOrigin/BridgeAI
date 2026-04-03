import { useState, useEffect, useCallback } from 'react'
import { Row, Col, Button, Modal, Form, Input, Select, message, Tooltip, Spin } from 'antd'
import {
  PlusOutlined,
  ApiOutlined,
  ReloadOutlined,
  DeleteOutlined,
  EditOutlined,
  LinkOutlined,
  ShoppingOutlined,
  ToolOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { McpConnector } from '../../types/chat'
import {
  getMcpConnectors,
  createMcpConnector,
  updateMcpConnector,
  deleteMcpConnector,
  testMcpConnector,
  getMcpConnectorTools,
} from '../../api/mcp'
import GlassCard from '../../components/GlassCard'
import StatusBadge from '../../components/StatusBadge'

interface MarketplaceItem {
  name: string
  description: string
  author: string
  downloads: number
  connectorType: string
  defaultEndpoint: string
  configFields: { name: string; label: string; required: boolean; type?: string; placeholder?: string; options?: { label: string; value: string }[] }[]
}

const MARKETPLACE: MarketplaceItem[] = [
  {
    name: '飞书',
    description: '连接飞书开放平台，访问消息、日历、文档等',
    author: 'Lark',
    downloads: 9200,
    connectorType: 'sse',
    defaultEndpoint: 'https://open.feishu.cn',
    configFields: [
      { name: 'app_id', label: 'App ID', required: true, placeholder: '飞书应用的 App ID' },
      { name: 'app_secret', label: 'App Secret', required: true, placeholder: '飞书应用的 App Secret' },
    ],
  },
  {
    name: '钉钉',
    description: '连接钉钉开放平台，管理群组、审批、通讯录等',
    author: 'DingTalk',
    downloads: 8500,
    connectorType: 'sse',
    defaultEndpoint: 'https://oapi.dingtalk.com',
    configFields: [
      { name: 'app_key', label: 'App Key', required: true, placeholder: '钉钉应用的 AppKey' },
      { name: 'app_secret', label: 'App Secret', required: true, placeholder: '钉钉应用的 AppSecret' },
    ],
  },
  {
    name: 'MySQL / PostgreSQL',
    description: '连接关系型数据库，执行查询和数据管理',
    author: 'Database',
    downloads: 12500,
    connectorType: 'stdio',
    defaultEndpoint: 'db-connector',
    configFields: [
      { name: 'db_type', label: '数据库类型', required: true, type: 'select', options: [{ label: 'PostgreSQL', value: 'postgresql' }, { label: 'MySQL', value: 'mysql' }] },
      { name: 'host', label: '主机地址', required: true, placeholder: '例如 127.0.0.1' },
      { name: 'port', label: '端口', required: true, placeholder: '例如 5432 或 3306' },
      { name: 'database', label: '数据库名', required: true, placeholder: '数据库名称' },
      { name: 'username', label: '用户名', required: true, placeholder: '数据库用户名' },
      { name: 'password', label: '密码', required: true, placeholder: '数据库密码' },
    ],
  },
  {
    name: 'HTTP API',
    description: '连接任意 HTTP/REST API 服务',
    author: 'Generic',
    downloads: 6700,
    connectorType: 'streamable_http',
    defaultEndpoint: '',
    configFields: [
      { name: 'base_url', label: 'Base URL', required: true, placeholder: 'https://api.example.com' },
      { name: 'headers', label: 'Headers (JSON)', required: false, type: 'textarea', placeholder: '{"Authorization": "Bearer xxx"}' },
    ],
  },
]

export default function MCPPage() {
  const { t } = useTranslation()
  const [connectors, setConnectors] = useState<McpConnector[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingConnector, setEditingConnector] = useState<McpConnector | null>(null)
  const [installItem, setInstallItem] = useState<MarketplaceItem | null>(null)
  const [installModalOpen, setInstallModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [installForm] = Form.useForm()

  const loadConnectors = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getMcpConnectors()
      setConnectors(data)
      // Batch-load tools for each connector to get actual tool counts
      const toolsPromises = data.map(async (conn) => {
        const tools = await getMcpConnectorTools(conn.id)
        return { id: conn.id, tools }
      })
      const toolsResults = await Promise.allSettled(toolsPromises)
      setConnectors((prev) =>
        prev.map((conn) => {
          const result = toolsResults.find((_r, i) => data[i]?.id === conn.id)
          if (result?.status === 'fulfilled' && result.value.tools.length > 0) {
            return {
              ...conn,
              tools: result.value.tools.map((t) => ({
                name: t.name,
                description: t.description || '',
                inputSchema: t.input_schema || {},
              })),
            }
          }
          return conn
        }),
      )
    } catch (err) {
      message.error(`${t('mcp.loadFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadConnectors()
  }, [loadConnectors])

  const handleAdd = async () => {
    try {
      const values = await form.validateFields()
      if (editingConnector) {
        // Edit mode
        const updated = await updateMcpConnector(editingConnector.id, values)
        setConnectors((prev) =>
          prev.map((c) => (c.id === editingConnector.id ? updated : c)),
        )
        message.success(t('mcp.updated'))
      } else {
        const created = await createMcpConnector(values)
        setConnectors((prev) => [...prev, created])
        message.success(t('mcp.added'))
      }
      setModalOpen(false)
      setEditingConnector(null)
      form.resetFields()
    } catch (err) {
      if (err instanceof Error) {
        message.error(`${editingConnector ? t('mcp.updateFailed') : t('mcp.addFailed')}: ${err.message}`)
      }
    }
  }

  const handleEdit = (conn: McpConnector) => {
    setEditingConnector(conn)
    form.setFieldsValue({
      name: conn.name,
      description: conn.description,
      type: conn.type,
      endpoint: conn.endpoint,
    })
    setModalOpen(true)
  }

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: t('common.confirmDelete'),
      content: t('mcp.confirmDeleteContent'),
      okType: 'danger',
      okText: t('common.delete'),
      cancelText: t('common.cancel'),
      onOk: async () => {
        try {
          await deleteMcpConnector(id)
          setConnectors((prev) => prev.filter((c) => c.id !== id))
          message.success(t('common.deleteSuccess'))
        } catch (err) {
          message.error(`${t('common.deleteFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
        }
      },
    })
  }

  const handleTest = async (id: string) => {
    message.loading({ content: t('mcp.testConnecting'), key: 'test-conn' })
    const result = await testMcpConnector(id)
    if (result.success) {
      setConnectors((prev) =>
        prev.map((c) => (c.id === id ? { ...c, status: 'connected' as const } : c)),
      )
      message.success({ content: t('mcp.testSuccess'), key: 'test-conn' })
    } else {
      message.error({ content: result.message, key: 'test-conn' })
    }
  }

  const handleInstall = (item: MarketplaceItem) => {
    setInstallItem(item)
    installForm.resetFields()
    installForm.setFieldsValue({ name: item.name, endpoint: item.defaultEndpoint })
    setInstallModalOpen(true)
  }

  const handleInstallSubmit = async () => {
    if (!installItem) return
    try {
      const values = await installForm.validateFields()
      // Collect config fields into auth_config
      const configData: Record<string, unknown> = {}
      for (const field of installItem.configFields) {
        if (values[field.name] !== undefined && values[field.name] !== '') {
          configData[field.name] = values[field.name]
        }
      }
      const payload = {
        name: values.name,
        description: installItem.description,
        type: installItem.connectorType,
        endpoint: values.endpoint,
        config: configData,
      }
      await createMcpConnector(payload)
      setInstallModalOpen(false)
      installForm.resetFields()
      setInstallItem(null)
      message.success(t('mcp.installSuccess', { name: installItem.name }))
      await loadConnectors()
    } catch (err) {
      if (err instanceof Error) {
        message.error(`${t('mcp.installFailed')}: ${err.message}`)
      }
    }
  }

  return (
    <div className="animate-fade-in">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <h2 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
          {t('mcp.title')}
        </h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          {t('mcp.add')}
        </Button>
      </div>

      {/* Active Connectors */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 32, color: '#6366f1' }} />} />
          <div style={{ color: '#94a3b8', marginTop: 16 }}>{t('mcp.loadingList')}</div>
        </div>
      ) : (
        <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
          {connectors.map((conn) => (
            <Col xs={24} sm={12} lg={8} key={conn.id}>
              <GlassCard>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 10,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(34,197,94,0.1)',
                      color: '#22c55e',
                      fontSize: 20,
                    }}
                  >
                    <ApiOutlined />
                  </div>
                  <StatusBadge status={conn.status} />
                </div>

                <h3 style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                  {conn.name}
                </h3>
                <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 8, lineHeight: 1.5 }}>
                  {conn.description}
                </p>

                <div style={{ fontSize: 12, color: '#64748b', marginBottom: 4 }}>
                  <LinkOutlined style={{ marginRight: 4 }} />
                  {conn.type.toUpperCase()} | {t('mcp.toolCount', { count: conn.tools.length })}
                </div>
                {conn.tools.length > 0 && (
                  <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {conn.tools.map((tool) => (
                      <Tooltip title={tool.description} key={tool.name}>
                        <span
                          style={{
                            fontSize: 11,
                            padding: '2px 8px',
                            borderRadius: 4,
                            background: 'rgba(99,102,241,0.08)',
                            color: '#a78bfa',
                            border: '1px solid rgba(99,102,241,0.15)',
                          }}
                        >
                          <ToolOutlined style={{ marginRight: 3, fontSize: 10 }} />
                          {tool.name}
                        </span>
                      </Tooltip>
                    ))}
                  </div>
                )}

                <div
                  style={{
                    display: 'flex',
                    gap: 8,
                    borderTop: '1px solid rgba(148,163,184,0.1)',
                    paddingTop: 12,
                    marginTop: 12,
                  }}
                >
                  <Button
                    type="text"
                    size="small"
                    icon={<ReloadOutlined />}
                    onClick={() => handleTest(conn.id)}
                    style={{ color: '#22c55e', fontSize: 12 }}
                  >
                    {t('common.test')}
                  </Button>
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => handleEdit(conn)}
                    style={{ color: '#6366f1', fontSize: 12 }}
                  >
                    {t('common.edit')}
                  </Button>
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => handleDelete(conn.id)}
                    style={{ color: '#ef4444', fontSize: 12 }}
                  >
                    {t('common.delete')}
                  </Button>
                </div>
              </GlassCard>
            </Col>
          ))}
          {connectors.length === 0 && !loading && (
            <Col span={24}>
              <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>
                {t('mcp.emptyHint')}
              </div>
            </Col>
          )}
        </Row>
      )}

      {/* Marketplace */}
      <h3 style={{ fontSize: 17, fontWeight: 600, color: '#e2e8f0', marginBottom: 16 }}>
        <ShoppingOutlined style={{ marginRight: 8, color: '#6366f1' }} />
        {t('mcp.marketplace')}
      </h3>
      <Row gutter={[16, 16]}>
        {MARKETPLACE.map((item) => (
          <Col xs={24} sm={12} lg={6} key={item.name}>
            <GlassCard>
              <h4 style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                {item.name}
              </h4>
              <p style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>
                {item.description}
              </p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: '#64748b' }}>
                  {item.author} | {item.downloads.toLocaleString()} {t('mcp.downloads')}
                </span>
                <Button type="primary" size="small" ghost style={{ fontSize: 12 }} onClick={() => handleInstall(item)}>
                  {t('common.install')}
                </Button>
              </div>
            </GlassCard>
          </Col>
        ))}
      </Row>

      {/* Add/Edit Modal */}
      <Modal
        title={editingConnector ? t('mcp.editTitle') : t('mcp.addTitle')}
        open={modalOpen}
        onOk={handleAdd}
        onCancel={() => { setModalOpen(false); setEditingConnector(null); form.resetFields() }}
        okText={editingConnector ? t('common.save') : t('mcp.add')}
        cancelText={t('common.cancel')}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label={t('mcp.nameLabel')} rules={[{ required: true, message: t('mcp.nameRequired') }]}>
            <Input placeholder={t('mcp.namePlaceholder')} />
          </Form.Item>
          <Form.Item name="description" label={t('mcp.descLabel')} rules={[{ required: true, message: t('mcp.descRequired') }]}>
            <Input placeholder={t('mcp.descPlaceholder')} />
          </Form.Item>
          <Form.Item name="type" label={t('mcp.typeLabel')} rules={[{ required: true }]} initialValue="stdio">
            <Select
              options={[
                { label: 'STDIO', value: 'stdio' },
                { label: 'SSE', value: 'sse' },
                { label: 'Streamable HTTP', value: 'streamable_http' },
              ]}
            />
          </Form.Item>
          <Form.Item name="endpoint" label={t('mcp.endpointLabel')} rules={[{ required: true, message: t('mcp.endpointRequired') }]}>
            <Input placeholder={t('mcp.endpointPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Install from Marketplace Modal */}
      <Modal
        title={t('mcp.installTitle', { name: installItem?.name || '' })}
        open={installModalOpen}
        onOk={handleInstallSubmit}
        onCancel={() => { setInstallModalOpen(false); setInstallItem(null) }}
        okText={t('common.install')}
        cancelText={t('common.cancel')}
      >
        <Form form={installForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label={t('mcp.connectorName')} rules={[{ required: true, message: t('mcp.nameRequired') }]}>
            <Input placeholder={t('mcp.connectorNamePlaceholder')} />
          </Form.Item>
          <Form.Item name="endpoint" label={t('mcp.endpointUrl')} rules={[{ required: true, message: t('mcp.endpointRequired') }]}>
            <Input placeholder={t('mcp.endpointUrlPlaceholder')} />
          </Form.Item>
          {installItem?.configFields.map((field) => (
            <Form.Item
              key={field.name}
              name={field.name}
              label={field.label}
              rules={field.required ? [{ required: true, message: t('mcp.pleaseInput', { label: field.label }) }] : []}
            >
              {field.type === 'select' ? (
                <Select options={field.options} placeholder={t('mcp.pleaseSelect', { label: field.label })} />
              ) : field.type === 'textarea' ? (
                <Input.TextArea rows={3} placeholder={field.placeholder} />
              ) : (
                <Input placeholder={field.placeholder} />
              )}
            </Form.Item>
          ))}
        </Form>
      </Modal>
    </div>
  )
}
