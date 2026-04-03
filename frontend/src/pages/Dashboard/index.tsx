import { useState, useEffect } from 'react'
import { Row, Col, Statistic, Spin, message } from 'antd'
import {
  MessageOutlined,
  RobotOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { useTranslation } from 'react-i18next'
import GlassCard from '../../components/GlassCard'
import { getSystemStats, type SystemStats } from '../../api/system'

const PIE_COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#22c55e', '#f59e0b']

export default function DashboardPage() {
  const { t } = useTranslation()
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      try {
        const data = await getSystemStats()
        if (!cancelled) setStats(data)
      } catch (err) {
        message.error(`${t('dashboard.loadFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadData()
    return () => { cancelled = true }
  }, [t])

  if (loading) {
    return (
      <div className="animate-fade-in" style={{ textAlign: 'center', padding: 120 }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 32, color: '#6366f1' }} />} />
        <div style={{ color: '#94a3b8', marginTop: 16 }}>{t('dashboard.loadingData')}</div>
      </div>
    )
  }

  const cards = [
    {
      title: t('dashboard.conversations'),
      value: stats?.total_conversations ?? 0,
      suffix: t('common.unit'),
      icon: <MessageOutlined />,
      color: '#6366f1',
    },
    {
      title: t('dashboard.messages'),
      value: stats?.total_messages ?? 0,
      suffix: t('common.items'),
      icon: <FileTextOutlined />,
      color: '#22c55e',
    },
    {
      title: t('dashboard.agents'),
      value: stats?.total_agents ?? 0,
      suffix: t('common.unit'),
      icon: <RobotOutlined />,
      color: '#8b5cf6',
    },
    {
      title: t('dashboard.mcpConnections'),
      value: stats?.total_mcp_connectors ?? 0,
      suffix: t('common.unit'),
      icon: <ApiOutlined />,
      color: '#f59e0b',
    },
    {
      title: t('dashboard.knowledgeBase'),
      value: stats?.total_knowledge_bases ?? 0,
      suffix: t('common.unit'),
      icon: <DatabaseOutlined />,
      color: '#ec4899',
    },
    {
      title: t('dashboard.documents'),
      value: stats?.total_documents ?? 0,
      suffix: t('common.copies'),
      icon: <ThunderboltOutlined />,
      color: '#14b8a6',
    },
  ]

  // Format daily_usage dates for display (MM-DD)
  const dailyUsage = (stats?.daily_usage ?? []).map((d) => ({
    ...d,
    date: d.date.slice(5), // "2026-03-26" -> "03-26"
  }))

  // Transform distributions for pie charts
  const intentData = (stats?.intent_distribution ?? []).map((d) => ({
    name: d.intent ?? 'unknown',
    value: d.count,
  }))

  const emotionData = (stats?.emotion_distribution ?? []).map((d) => ({
    name: d.emotion ?? 'unknown',
    value: d.count,
  }))

  // Transform model usage for bar chart
  const modelData = (stats?.model_usage ?? []).map((d) => ({
    name: d.model ?? 'unknown',
    value: d.count,
  }))

  const tooltipStyle = {
    background: '#1a2332',
    border: '1px solid rgba(148,163,184,0.2)',
    borderRadius: 8,
    color: '#e2e8f0',
  }

  return (
    <div className="animate-fade-in">
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24, color: '#f1f5f9' }}>
        {t('dashboard.title')}
      </h2>

      {/* Stats Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {cards.map((card) => (
          <Col xs={24} sm={12} lg={4} key={card.title}>
            <GlassCard hoverable={false}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 8 }}>
                    {card.title}
                  </div>
                  <Statistic
                    value={card.value}
                    suffix={card.suffix}
                    valueStyle={{ color: '#f1f5f9', fontSize: 28, fontWeight: 700 }}
                  />
                </div>
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 12,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: `${card.color}26`,
                    color: card.color,
                    fontSize: 22,
                  }}
                >
                  {card.icon}
                </div>
              </div>
            </GlassCard>
          </Col>
        ))}
      </Row>

      {/* Charts Row 1: Trends + Intent Pie */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {/* Usage Trend */}
        <Col xs={24} lg={16}>
          <GlassCard hoverable={false}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 20, color: '#e2e8f0' }}>
              {t('dashboard.messageTrend')}
            </div>
            {dailyUsage.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={dailyUsage}>
                  <defs>
                    <linearGradient id="colorMessages" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area
                    type="monotone"
                    dataKey="messages"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorMessages)"
                    name={t('dashboard.messageCount')}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: 80, color: '#64748b' }}>{t('dashboard.noMessageData')}</div>
            )}
          </GlassCard>
        </Col>

        {/* Intent Distribution */}
        <Col xs={24} lg={8}>
          <GlassCard hoverable={false}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 20, color: '#e2e8f0' }}>
              {t('dashboard.intentDistribution')}
            </div>
            {intentData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={intentData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {intentData.map((_, index) => (
                        <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center' }}>
                  {intentData.map((item, i) => (
                    <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94a3b8' }}>
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      {item.name} ({item.value})
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: 80, color: '#64748b' }}>{t('dashboard.noIntentData')}</div>
            )}
          </GlassCard>
        </Col>
      </Row>

      {/* Charts Row 2: Emotion Pie + Model Bar */}
      <Row gutter={[16, 16]}>
        {/* Emotion Distribution */}
        <Col xs={24} lg={8}>
          <GlassCard hoverable={false}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 20, color: '#e2e8f0' }}>
              {t('dashboard.emotionDistribution')}
            </div>
            {emotionData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={emotionData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {emotionData.map((_, index) => (
                        <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center' }}>
                  {emotionData.map((item, i) => (
                    <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94a3b8' }}>
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      {item.name} ({item.value})
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: 80, color: '#64748b' }}>{t('dashboard.noEmotionData')}</div>
            )}
          </GlassCard>
        </Col>

        {/* Model Usage Bar Chart */}
        <Col xs={24} lg={16}>
          <GlassCard hoverable={false}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 20, color: '#e2e8f0' }}>
              {t('dashboard.modelUsage')}
            </div>
            {modelData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={modelData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis type="number" stroke="#64748b" fontSize={12} />
                  <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={12} width={140} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="value" name={t('dashboard.callCount')} radius={[0, 4, 4, 0]}>
                    {modelData.map((_, index) => (
                      <Cell
                        key={index}
                        fill={PIE_COLORS[index % PIE_COLORS.length]}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: 80, color: '#64748b' }}>{t('dashboard.noModelData')}</div>
            )}
          </GlassCard>
        </Col>
      </Row>
    </div>
  )
}
