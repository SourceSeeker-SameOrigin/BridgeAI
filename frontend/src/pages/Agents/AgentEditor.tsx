import { useState, useEffect } from 'react'
import { Drawer, Form, Input, Select, Slider, Button, Space, Divider, Typography, Checkbox } from 'antd'
import { CopyOutlined, AppstoreOutlined, DatabaseOutlined, ApiOutlined, ThunderboltOutlined, TeamOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { Agent } from '../../types/agent'
import { getAgents } from '../../api/agents'
import { getSystemModels, type SystemModel } from '../../api/system'
import { getInstalledPlugins } from '../../api/plugins'
import type { InstalledPlugin } from '../../api/plugins'
import { getMcpConnectors } from '../../api/mcp'
import { getKnowledgeBases } from '../../api/knowledge'
import { getAgentTemplates, type AgentTemplate } from '../../api/agents'
import type { McpConnector, KnowledgeBase } from '../../types/chat'

const { TextArea } = Input
const { Text } = Typography

interface AgentEditorProps {
  open: boolean
  agent: Agent | null
  onClose: () => void
  onSave: (values: Partial<Agent>) => void
}

const FALLBACK_MODELS = [
  { label: 'DeepSeek Chat', value: 'deepseek-chat' },
  { label: 'DeepSeek Reasoner', value: 'deepseek-reasoner' },
  { label: 'Qwen Plus', value: 'qwen-plus' },
  { label: 'Qwen Max', value: 'qwen-max' },
]

export default function AgentEditor({ open, agent, onClose, onSave }: AgentEditorProps) {
  const { t } = useTranslation()
  const [form] = Form.useForm()
  const [selectedTemplate, setSelectedTemplate] = useState<string | undefined>(undefined)
  const [models, setModels] = useState(FALLBACK_MODELS)
  const [installedPlugins, setInstalledPlugins] = useState<InstalledPlugin[]>([])
  const [mcpConnectors, setMcpConnectors] = useState<McpConnector[]>([])
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [agentTemplates, setAgentTemplates] = useState<AgentTemplate[]>([])
  const [allAgents, setAllAgents] = useState<Agent[]>([])

  const PROMPT_TEMPLATES = [
    {
      label: t('agents.templateCustomerService'),
      value: 'customer_service',
      description: t('agents.templateCustomerServiceDesc'),
      prompt: `你是一名专业的客服助手。请遵循以下原则：
1. 始终保持礼貌、耐心和专业的态度
2. 准确理解客户问题，必要时进行确认
3. 提供清晰、简洁的解决方案
4. 无法解决的问题及时升级给人工客服
5. 记录客户反馈，持续改进服务质量

注意事项：
- 不要编造信息，不确定时如实告知
- 涉及敏感操作（退款、账号变更等）需二次确认
- 对话结束前确认客户问题已解决`,
    },
    {
      label: t('agents.templateDataAnalyst'),
      value: 'data_analyst',
      description: t('agents.templateDataAnalystDesc'),
      prompt: `你是一名资深数据分析师。请遵循以下原则：
1. 基于数据事实进行分析，避免主观臆断
2. 使用 SQL 查询数据时注意性能，避免全表扫描
3. 分析结果以结构化方式呈现（表格、关键指标等）
4. 主动发现数据异常并提出预警
5. 给出可操作的业务建议

输出格式：
- 先给出结论摘要
- 再展示详细数据支撑
- 最后提供改进建议`,
    },
    {
      label: t('agents.templateDocAssistant'),
      value: 'doc_assistant',
      description: t('agents.templateDocAssistantDesc'),
      prompt: `你是一名专业的文档撰写助手。请遵循以下原则：
1. 根据目标受众调整写作风格和深度
2. 结构清晰，使用标题、列表和段落合理组织内容
3. 语言准确、简洁，避免冗余表达
4. 确保逻辑连贯，论据充分
5. 校对语法和格式错误

支持的文档类型：技术文档、会议纪要、产品需求、工作报告等`,
    },
    {
      label: t('agents.templateCodeReviewer'),
      value: 'code_reviewer',
      description: t('agents.templateCodeReviewerDesc'),
      prompt: `你是一名高级代码审查工程师。请遵循以下原则：
1. 检查代码逻辑正确性和边界条件处理
2. 关注安全隐患（注入、XSS、敏感信息泄露等）
3. 评估代码可读性和可维护性
4. 检查是否符合团队编码规范
5. 提供具体的改进建议和示例代码

审查维度：
- 功能正确性 / 安全性 / 性能 / 可读性 / 测试覆盖`,
    },
    {
      label: t('agents.templateApproval'),
      value: 'approval_assistant',
      description: t('agents.templateApprovalDesc'),
      prompt: `你是一名智能审批助手。请遵循以下原则：
1. 根据审批规则自动检查申请内容的合规性
2. 标注异常项并说明原因
3. 对超出权限范围的申请给出风险提示
4. 提供审批建议但不代替人工决策
5. 记录审批过程，确保可追溯

注意事项：
- 严格遵守审批权限和流程规定
- 涉及金额/权限变更需要双重验证
- 敏感审批需提醒审批人重点关注`,
    },
    {
      label: t('agents.templateCustom'),
      value: 'custom',
      description: t('agents.templateCustomDesc'),
      prompt: '',
    },
  ]

  useEffect(() => {
    getSystemModels()
      .then((data: SystemModel[]) => {
        const available = data
          .filter((m) => m.available)
          .map((m) => ({ label: m.name, value: m.id }))
        if (available.length > 0) {
          setModels(available)
        }
      })
      .catch(() => {
        // Use fallback models
      })

    getInstalledPlugins()
      .then(setInstalledPlugins)
      .catch(() => {
        // Plugins may not be available
      })

    getMcpConnectors()
      .then(setMcpConnectors)
      .catch(() => {
        // MCP connectors may not be available
      })

    getKnowledgeBases()
      .then(setKnowledgeBases)
      .catch(() => {
        // Knowledge bases may not be available
      })

    getAgentTemplates()
      .then(setAgentTemplates)
      .catch(() => {
        // Templates may not be available
      })

    getAgents()
      .then(setAllAgents)
      .catch(() => {
        // Agents list may not be available
      })
  }, [])

  const handleOpen = () => {
    if (agent) {
      form.setFieldsValue(agent)
      setSelectedTemplate(undefined)
    } else {
      form.resetFields()
      setSelectedTemplate(undefined)
    }
  }

  const handleTemplateChange = (value: string) => {
    setSelectedTemplate(value)
    const tpl = PROMPT_TEMPLATES.find((t) => t.value === value)
    if (tpl) {
      form.setFieldsValue({ systemPrompt: tpl.prompt })
    }
  }

  const handleAgentTemplateChange = (key: string) => {
    const tpl = agentTemplates.find((t) => t.key === key)
    if (tpl) {
      form.setFieldsValue({
        name: tpl.name,
        description: tpl.description,
        systemPrompt: tpl.system_prompt,
        model: tpl.model_config?.model_name || 'deepseek-chat',
        temperature: tpl.model_config?.temperature ?? 0.7,
        maxTokens: tpl.model_config?.max_tokens ?? 4096,
      })
    }
  }

  return (
    <Drawer
      title={agent ? t('agents.edit') : t('agents.create')}
      placement="right"
      width={560}
      open={open}
      onClose={onClose}
      afterOpenChange={(visible) => visible && handleOpen()}
      styles={{
        header: {
          borderBottom: '1px solid rgba(148,163,184,0.1)',
          color: '#e2e8f0',
        },
        body: { background: '#111827' },
      }}
      extra={
        <Space>
          <Button onClick={onClose}>{t('common.cancel')}</Button>
          <Button type="primary" onClick={() => form.submit()}>
            {t('common.save')}
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={onSave}
        initialValues={{
          temperature: 0.7,
          maxTokens: 4096,
          model: 'deepseek-chat',
        }}
      >
        {!agent && agentTemplates.length > 0 && (
          <Form.Item
            label={
              <span style={{ color: '#cbd5e1' }}>
                <ThunderboltOutlined style={{ marginRight: 4 }} />
                {t('agents.fromTemplate')}
              </span>
            }
          >
            <Select
              placeholder={t('agents.fromTemplatePlaceholder')}
              allowClear
              onChange={handleAgentTemplateChange}
              options={agentTemplates.map((t) => ({
                label: t.name,
                value: t.key,
              }))}
              optionRender={(option) => {
                const tpl = agentTemplates.find((t) => t.key === option.value)
                return (
                  <div>
                    <div>{option.label}</div>
                    <div style={{ fontSize: 11, color: '#94a3b8' }}>{tpl?.description}</div>
                  </div>
                )
              }}
            />
          </Form.Item>
        )}

        <Form.Item
          name="name"
          label={<span style={{ color: '#cbd5e1' }}>{t('common.name')}</span>}
          rules={[{ required: true, message: t('agents.nameRequired') }]}
        >
          <Input placeholder={t('agents.namePlaceholder')} />
        </Form.Item>

        <Form.Item
          name="description"
          label={<span style={{ color: '#cbd5e1' }}>{t('common.description')}</span>}
          rules={[{ required: true, message: t('agents.descRequired') }]}
        >
          <TextArea rows={2} placeholder={t('agents.descPlaceholder')} />
        </Form.Item>

        <Form.Item
          name="model"
          label={<span style={{ color: '#cbd5e1' }}>{t('common.model')}</span>}
          rules={[{ required: true }]}
        >
          <Select options={models} />
        </Form.Item>

        <Divider style={{ borderColor: 'rgba(148,163,184,0.15)', margin: '16px 0' }}>
          <Text style={{ color: '#94a3b8', fontSize: 12 }}>
            <CopyOutlined style={{ marginRight: 4 }} />
            {t('agents.systemPromptSection')}
          </Text>
        </Divider>

        <Form.Item
          label={<span style={{ color: '#cbd5e1' }}>{t('agents.promptTemplate')}</span>}
        >
          <Select
            placeholder={t('agents.promptTemplatePlaceholder')}
            value={selectedTemplate}
            onChange={handleTemplateChange}
            allowClear
            onClear={() => setSelectedTemplate(undefined)}
            options={PROMPT_TEMPLATES.map((t) => ({
              label: t.label,
              value: t.value,
              title: t.description,
            }))}
            optionRender={(option) => {
              const tpl = PROMPT_TEMPLATES.find((t) => t.value === option.value)
              return (
                <div>
                  <div>{option.label}</div>
                  <div style={{ fontSize: 11, color: '#94a3b8' }}>{tpl?.description}</div>
                </div>
              )
            }}
          />
        </Form.Item>

        <Form.Item
          name="systemPrompt"
          label={<span style={{ color: '#cbd5e1' }}>{t('agents.systemPrompt')}</span>}
          rules={[{ required: true, message: t('agents.systemPromptRequired') }]}
        >
          <TextArea
            rows={12}
            placeholder={t('agents.systemPromptPlaceholder')}
            style={{
              fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
              fontSize: 13,
              lineHeight: '1.6',
              minHeight: 240,
              background: 'rgba(0,0,0,0.2)',
              borderColor: 'rgba(148,163,184,0.15)',
              padding: '12px 16px',
            }}
          />
        </Form.Item>

        <Divider style={{ borderColor: 'rgba(148,163,184,0.15)', margin: '16px 0' }}>
          <Text style={{ color: '#94a3b8', fontSize: 12 }}>
            <TeamOutlined style={{ marginRight: 4 }} />
            {t('agents.subAgentSection', '子 Agent 设置')}
          </Text>
        </Divider>

        <Form.Item
          name="parentAgentId"
          label={<span style={{ color: '#cbd5e1' }}>{t('agents.parentAgent', '父级 Agent')}</span>}
        >
          <Select
            placeholder={t('agents.parentAgentPlaceholder', '选择父级 Agent（可选）')}
            allowClear
            options={allAgents
              .filter((a) => a.id !== agent?.id)
              .map((a) => ({
                label: a.name,
                value: a.id,
              }))}
          />
        </Form.Item>

        <Divider style={{ borderColor: 'rgba(148,163,184,0.15)', margin: '16px 0' }} />

        <Form.Item
          name="temperature"
          label={<span style={{ color: '#cbd5e1' }}>{t('agents.temperature')}</span>}
        >
          <Slider
            min={0}
            max={2}
            step={0.1}
            marks={{ 0: t('agents.tempPrecise'), 1: t('agents.tempBalanced'), 2: t('agents.tempCreative') }}
          />
        </Form.Item>

        <Form.Item
          name="maxTokens"
          label={<span style={{ color: '#cbd5e1' }}>{t('agents.maxTokens')}</span>}
        >
          <Select
            options={[
              { label: '1024', value: 1024 },
              { label: '2048', value: 2048 },
              { label: '4096', value: 4096 },
              { label: '8192', value: 8192 },
              { label: '16384', value: 16384 },
            ]}
          />
        </Form.Item>

        <Divider style={{ borderColor: 'rgba(148,163,184,0.15)', margin: '16px 0' }}>
          <Text style={{ color: '#94a3b8', fontSize: 12 }}>
            <DatabaseOutlined style={{ marginRight: 4 }} />
            {t('agents.knowledgeBaseBinding')}
          </Text>
        </Divider>

        <Form.Item
          name="knowledgeBaseId"
          label={<span style={{ color: '#cbd5e1' }}>{t('knowledge.title')}</span>}
        >
          <Select
            placeholder={t('agents.knowledgeBasePlaceholder')}
            allowClear
            options={knowledgeBases.map((kb) => ({
              label: `${kb.name} (${t('agents.knowledgeBaseDocCount', { count: kb.documentCount })})`,
              value: kb.id,
            }))}
          />
        </Form.Item>

        <Divider style={{ borderColor: 'rgba(148,163,184,0.15)', margin: '16px 0' }}>
          <Text style={{ color: '#94a3b8', fontSize: 12 }}>
            <ApiOutlined style={{ marginRight: 4 }} />
            {t('agents.mcpToolBinding')}
          </Text>
        </Divider>

        <Form.Item
          name="tools"
          label={<span style={{ color: '#cbd5e1' }}>{t('agents.mcpConnectors')}</span>}
        >
          <Checkbox.Group
            style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            options={mcpConnectors.map((c) => ({
              label: (
                <span style={{ color: '#cbd5e1' }}>
                  {c.name}
                  <span style={{ color: '#64748b', fontSize: 11, marginLeft: 6 }}>
                    {c.type.toUpperCase()} | {c.status === 'connected' ? t('agents.connected') : t('agents.disconnected')}
                  </span>
                </span>
              ),
              value: c.id,
            }))}
          />
        </Form.Item>

        {installedPlugins.length > 0 && (
          <>
            <Divider style={{ borderColor: 'rgba(148,163,184,0.15)', margin: '16px 0' }}>
              <Text style={{ color: '#94a3b8', fontSize: 12 }}>
                <AppstoreOutlined style={{ marginRight: 4 }} />
                {t('agents.pluginBinding')}
              </Text>
            </Divider>

            <Form.Item
              name="plugins"
              label={<span style={{ color: '#cbd5e1' }}>{t('agents.bindPlugins')}</span>}
            >
              <Checkbox.Group
                style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
                options={installedPlugins.map((p) => ({
                  label: (
                    <span style={{ color: '#cbd5e1' }}>
                      {p.plugin_name}
                      <span style={{ color: '#64748b', fontSize: 11, marginLeft: 6 }}>
                        v{p.plugin_version}
                      </span>
                    </span>
                  ),
                  value: p.plugin_name,
                }))}
              />
            </Form.Item>
          </>
        )}
      </Form>
    </Drawer>
  )
}
