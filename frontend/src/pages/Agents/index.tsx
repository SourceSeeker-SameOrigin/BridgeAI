import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Row, Col, Button, message, Modal, Spin } from 'antd'
import {
  PlusOutlined,
  RobotOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { Agent } from '../../types/agent'
import { getAgents, createAgent, updateAgent, deleteAgent } from '../../api/agents'
import GlassCard from '../../components/GlassCard'
import StatusBadge from '../../components/StatusBadge'
import AgentEditor from './AgentEditor'

export default function AgentsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(false)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null)

  const loadAgents = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getAgents()
      setAgents(data)
    } catch (err) {
      message.error(`${t('agents.loadFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadAgents()
  }, [loadAgents])

  const handleCreate = () => {
    setEditingAgent(null)
    setEditorOpen(true)
  }

  const handleEdit = (agent: Agent) => {
    setEditingAgent(agent)
    setEditorOpen(true)
  }

  const handleDelete = (agent: Agent) => {
    Modal.confirm({
      title: t('common.confirmDelete'),
      content: t('agents.confirmDeleteContent', { name: agent.name }),
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteAgent(agent.id)
          setAgents((prev) => prev.filter((a) => a.id !== agent.id))
          message.success(t('common.deleteSuccess'))
        } catch (err) {
          message.error(`${t('common.deleteFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
        }
      },
    })
  }

  const handleSave = async (values: Partial<Agent> & { knowledgeBaseId?: string }) => {
    try {
      if (editingAgent) {
        const updated = await updateAgent({
          id: editingAgent.id,
          name: values.name,
          description: values.description,
          model: values.model,
          systemPrompt: values.systemPrompt,
          temperature: values.temperature,
          maxTokens: values.maxTokens,
          tools: values.tools,
          plugins: values.plugins,
          status: values.status,
          knowledgeBaseId: values.knowledgeBaseId,
          parentAgentId: values.parentAgentId,
        })
        setAgents((prev) =>
          prev.map((a) => (a.id === editingAgent.id ? updated : a)),
        )
        message.success(t('common.updateSuccess'))
      } else {
        const created = await createAgent({
          name: values.name || '',
          description: values.description || '',
          model: values.model || 'deepseek-v4-pro',
          systemPrompt: values.systemPrompt || '',
          temperature: values.temperature,
          maxTokens: values.maxTokens,
          tools: values.tools,
          plugins: values.plugins,
          knowledgeBaseId: values.knowledgeBaseId,
          parentAgentId: values.parentAgentId,
        })
        setAgents((prev) => [...prev, created])
        message.success(t('common.createSuccess'))
      }
      setEditorOpen(false)
    } catch (err) {
      message.error(`${t('common.saveFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
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
          {t('agents.title')}
        </h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          {t('agents.create')}
        </Button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 32, color: '#6366f1' }} />} />
          <div style={{ color: '#94a3b8', marginTop: 16 }}>{t('agents.loadingList')}</div>
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {agents.map((agent) => (
            <Col xs={24} sm={12} lg={8} xl={6} key={agent.id}>
              <GlassCard>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: 12,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(99,102,241,0.15)',
                      color: '#818cf8',
                      fontSize: 22,
                    }}
                  >
                    <RobotOutlined />
                  </div>
                  <StatusBadge status={agent.status} />
                </div>

                <h3
                  style={{
                    fontSize: 16,
                    fontWeight: 600,
                    color: '#e2e8f0',
                    marginBottom: 6,
                  }}
                >
                  {agent.name}
                </h3>
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
                  }}
                >
                  {agent.description}
                </p>

                <div style={{ fontSize: 12, color: '#64748b', marginBottom: 12 }}>
                  {t('agents.modelLabel')}: {agent.model} | {t('agents.toolsLabel')}: {agent.tools.length}
                </div>

                <div
                  style={{
                    display: 'flex',
                    gap: 8,
                    borderTop: '1px solid rgba(148,163,184,0.1)',
                    paddingTop: 12,
                  }}
                >
                  <Button
                    type="text"
                    size="small"
                    icon={<PlayCircleOutlined />}
                    style={{ color: '#22c55e', fontSize: 12 }}
                    onClick={() => navigate(`/chat?agentId=${agent.id}`)}
                  >
                    {t('agents.run')}
                  </Button>
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    style={{ color: '#6366f1', fontSize: 12 }}
                    onClick={() => handleEdit(agent)}
                  >
                    {t('common.edit')}
                  </Button>
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    style={{ color: '#ef4444', fontSize: 12 }}
                    onClick={() => handleDelete(agent)}
                  >
                    {t('common.delete')}
                  </Button>
                </div>
              </GlassCard>
            </Col>
          ))}
          {agents.length === 0 && !loading && (
            <Col span={24}>
              <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
                {t('agents.emptyHint')}
              </div>
            </Col>
          )}
        </Row>
      )}

      <AgentEditor
        open={editorOpen}
        agent={editingAgent}
        onClose={() => setEditorOpen(false)}
        onSave={handleSave}
      />
    </div>
  )
}
