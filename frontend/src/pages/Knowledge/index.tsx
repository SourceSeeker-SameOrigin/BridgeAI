import { useState, useEffect, useCallback } from 'react'
import { Row, Col, Button, Table, Modal, Form, Input, Upload, message, Spin, List, Typography, Progress } from 'antd'
import {
  PlusOutlined,
  BookOutlined,
  UploadOutlined,
  FileTextOutlined,
  DeleteOutlined,
  FolderOpenOutlined,
  LoadingOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
// UploadFile type removed — using customRequest with raw File instead
import type { KnowledgeBase, KnowledgeDocument } from '../../types/chat'
import {
  getKnowledgeBases,
  createKnowledgeBase,
  deleteKnowledgeBase,
  getDocuments,
  uploadDocument,
  deleteDocument,
  searchKnowledgeBase,
} from '../../api/knowledge'
import GlassCard from '../../components/GlassCard'
import StatusBadge from '../../components/StatusBadge'

const { Text } = Typography

export default function KnowledgePage() {
  const { t } = useTranslation()
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null)
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [docsLoading, setDocsLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [searchModalOpen, setSearchModalOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Array<{ chunk_id: string; content: string; similarity: number; document_id?: string }>>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [uploadPercent, setUploadPercent] = useState<number | null>(null)
  const [form] = Form.useForm()

  const loadKnowledgeBases = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getKnowledgeBases()
      setKnowledgeBases(data)
    } catch (err) {
      message.error(`${t('knowledge.loadFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadKnowledgeBases()
  }, [loadKnowledgeBases])

  const loadDocuments = useCallback(async (kbId: string) => {
    setDocsLoading(true)
    try {
      const data = await getDocuments(kbId)
      setDocuments(data)
    } catch (err) {
      message.error(`${t('knowledge.docLoadFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
      setDocuments([])
    } finally {
      setDocsLoading(false)
    }
  }, [t])

  const handleSelectKb = useCallback((kb: KnowledgeBase) => {
    setSelectedKb(kb)
    loadDocuments(kb.id)
  }, [loadDocuments])

  const handleCreateKb = async () => {
    try {
      const values = await form.validateFields()
      const created = await createKnowledgeBase(values)
      setKnowledgeBases((prev) => [...prev, created])
      message.success(t('knowledge.createSuccess', { name: values.name }))
      setModalOpen(false)
      form.resetFields()
    } catch (err) {
      if (err instanceof Error) {
        message.error(`${t('common.createFailed')}: ${err.message}`)
      }
    }
  }

  const handleDeleteKb = async (kb: KnowledgeBase) => {
    Modal.confirm({
      title: t('common.confirmDelete'),
      content: t('knowledge.confirmDeleteContent', { name: kb.name }),
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteKnowledgeBase(kb.id)
          setKnowledgeBases((prev) => prev.filter((k) => k.id !== kb.id))
          if (selectedKb?.id === kb.id) {
            setSelectedKb(null)
            setDocuments([])
          }
          message.success(t('common.deleteSuccess'))
        } catch (err) {
          message.error(`${t('common.deleteFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
        }
      },
    })
  }

  const handleDeleteDoc = async (docId: string) => {
    if (!selectedKb) return
    try {
      await deleteDocument(selectedKb.id, docId)
      setDocuments((prev) => prev.filter((d) => d.id !== docId))
      message.success(t('knowledge.docDeleted'))
    } catch (err) {
      message.error(`${t('common.deleteFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    }
  }

  const handleSearch = async () => {
    if (!selectedKb || !searchQuery.trim()) return
    setSearchLoading(true)
    try {
      const data = await searchKnowledgeBase(selectedKb.id, searchQuery.trim(), 5)
      setSearchResults(data)
    } catch (err) {
      message.error(`${t('knowledge.searchFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
      setSearchResults([])
    } finally {
      setSearchLoading(false)
    }
  }

  const docColumns = [
    {
      title: t('knowledge.docName'),
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileTextOutlined style={{ color: '#6366f1' }} />
          {name}
        </span>
      ),
    },
    { title: t('knowledge.docType'), dataIndex: 'type', key: 'type', width: 80 },
    { title: t('knowledge.docSize'), dataIndex: 'size', key: 'size', width: 100 },
    {
      title: t('knowledge.docStatus'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: 'indexed' | 'indexing' | 'failed') => {
        const map = { indexed: 'ready', indexing: 'indexing', failed: 'error' } as const
        return <StatusBadge status={map[status]} />
      },
    },
    {
      title: t('knowledge.docAction'),
      key: 'action',
      width: 80,
      render: (_: unknown, record: KnowledgeDocument) => (
        <Button
          type="text"
          size="small"
          icon={<DeleteOutlined />}
          style={{ color: '#ef4444' }}
          onClick={() => handleDeleteDoc(record.id)}
        />
      ),
    },
  ]

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
          {t('knowledge.title')}
        </h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          {t('knowledge.create')}
        </Button>
      </div>

      {/* Knowledge Base Cards */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 32, color: '#6366f1' }} />} />
          <div style={{ color: '#94a3b8', marginTop: 16 }}>{t('knowledge.loadingList')}</div>
        </div>
      ) : (
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          {knowledgeBases.map((kb) => (
            <Col xs={24} sm={12} lg={8} key={kb.id}>
              <GlassCard onClick={() => handleSelectKb(kb)}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 10,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(139,92,246,0.12)',
                      color: '#a78bfa',
                      fontSize: 20,
                    }}
                  >
                    <BookOutlined />
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <StatusBadge status={kb.status} />
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      style={{ color: '#ef4444' }}
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteKb(kb)
                      }}
                    />
                  </div>
                </div>

                <h3 style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                  {kb.name}
                </h3>
                <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>
                  {kb.description || t('common.noDescription')}
                </p>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#64748b' }}>
                  <span>
                    <FolderOpenOutlined style={{ marginRight: 4 }} />
                    {t('knowledge.documentCount', { count: kb.documentCount })}
                  </span>
                  <span>{kb.totalSize}</span>
                </div>

                {kb.status === 'indexing' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                    <LoadingOutlined style={{ color: '#6366f1', fontSize: 14 }} />
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>{t('knowledge.indexing')}</span>
                  </div>
                )}
              </GlassCard>
            </Col>
          ))}
          {knowledgeBases.length === 0 && !loading && (
            <Col span={24}>
              <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>
                {t('knowledge.emptyHint')}
              </div>
            </Col>
          )}
        </Row>
      )}

      {/* Document List */}
      {selectedKb && (
        <GlassCard hoverable={false} style={{ padding: 0 }}>
          <div
            style={{
              padding: '16px 20px',
              borderBottom: '1px solid rgba(148,163,184,0.1)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', margin: 0 }}>
              {selectedKb.name} - {t('knowledge.docList')}
            </h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button
                icon={<SearchOutlined />}
                size="small"
                onClick={() => {
                  setSearchQuery('')
                  setSearchResults([])
                  setSearchModalOpen(true)
                }}
              >
                {t('knowledge.search')}
              </Button>
              <Upload
                showUploadList={false}
                customRequest={async ({ file, onSuccess, onError }) => {
                  setUploadPercent(0)
                  try {
                    const doc = await uploadDocument(
                      selectedKb.id,
                      file as File,
                      (info) => setUploadPercent(info.percent),
                    )
                    setDocuments((prev) => [doc, ...prev])
                    message.success(t('knowledge.uploadSuccess'))
                    onSuccess?.(doc)
                  } catch (err) {
                    message.error(`${t('knowledge.uploadFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
                    onError?.(err as Error)
                  } finally {
                    setUploadPercent(null)
                  }
                }}
                accept=".md,.txt,.pdf,.docx,.doc,.xlsx,.xls,.csv"
              >
                <Button icon={<UploadOutlined />} type="primary" ghost size="small">
                  {t('knowledge.upload')}
                </Button>
              </Upload>
            </div>
          </div>
          {uploadPercent !== null && (
            <div style={{ padding: '8px 20px' }}>
              <Progress
                percent={uploadPercent}
                strokeColor={{ from: '#6366f1', to: '#8b5cf6' }}
                trailColor="rgba(148,163,184,0.1)"
                size="small"
                status="active"
              />
            </div>
          )}
          <Table
            columns={docColumns}
            dataSource={documents}
            rowKey="id"
            pagination={false}
            size="small"
            loading={docsLoading}
            style={{ padding: '0 8px' }}
            locale={{ emptyText: t('knowledge.noDocuments') }}
          />
        </GlassCard>
      )}

      {/* Create Modal */}
      <Modal
        title={t('knowledge.createTitle')}
        open={modalOpen}
        onOk={handleCreateKb}
        onCancel={() => setModalOpen(false)}
        okText={t('common.create')}
        cancelText={t('common.cancel')}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label={t('knowledge.nameLabel')} rules={[{ required: true, message: t('knowledge.nameRequired') }]}>
            <Input placeholder={t('knowledge.namePlaceholder')} />
          </Form.Item>
          <Form.Item name="description" label={t('knowledge.descLabel')}>
            <Input.TextArea rows={3} placeholder={t('knowledge.descPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Search Test Modal */}
      <Modal
        title={t('knowledge.searchTitle', { name: selectedKb?.name || '' })}
        open={searchModalOpen}
        onCancel={() => setSearchModalOpen(false)}
        footer={null}
        width={640}
      >
        <div style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <Input
              placeholder={t('knowledge.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onPressEnter={handleSearch}
            />
            <Button
              type="primary"
              icon={<SearchOutlined />}
              onClick={handleSearch}
              loading={searchLoading}
            >
              {t('knowledge.searchButton')}
            </Button>
          </div>
          {searchResults.length > 0 && (
            <List
              dataSource={searchResults}
              renderItem={(item, index) => (
                <List.Item>
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text strong>#{index + 1}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {t('knowledge.similarity')}: {(item.similarity * 100).toFixed(1)}%
                      </Text>
                    </div>
                    <Text
                      style={{
                        fontSize: 13,
                        display: '-webkit-box',
                        WebkitLineClamp: 4,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {item.content}
                    </Text>
                  </div>
                </List.Item>
              )}
            />
          )}
          {searchResults.length === 0 && !searchLoading && searchQuery && (
            <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>
              {t('knowledge.noResults')}
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
