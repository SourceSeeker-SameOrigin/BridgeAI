import { useState, useEffect, useCallback } from 'react'
import { Tabs, Form, Input, Select, Switch, Button, Table, message, Tag, Spin, Progress, Modal, Popconfirm, Radio } from 'antd'
import {
  SettingOutlined,
  KeyOutlined,
  TeamOutlined,
  RobotOutlined,
  SaveOutlined,
  PlusOutlined,
  DeleteOutlined,
  EyeInvisibleOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DollarOutlined,
  LinkOutlined,
  CrownOutlined,
  CopyOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import GlassCard from '../../components/GlassCard'
import { getSystemModels, type SystemModel, updateSystemSettings, getSystemSettings } from '../../api/system'
import { getUsage, getPlan } from '../../api/billing'
import type { UsageSummary, PlanInfo } from '../../api/billing'
import { getChannelStatus } from '../../api/channels'
import type { ChannelStatus } from '../../api/channels'
import { getApiKeys, createApiKey, deleteApiKey, revokeApiKey, type ApiKeyItem } from '../../api/apiKeys'
import { getUsers, deleteUser, changeRole, inviteUser } from '../../api/users'
import { createOrder, payOrder, getOrders, type PaymentOrder } from '../../api/payment'
import type { User } from '../../types/common'

const PLAN_LABELS: Record<string, { label: string; color: string }> = {
  free: { label: '免费版', color: '#64748b' },
  pro: { label: 'Pro 版', color: '#6366f1' },
  enterprise: { label: '企业版', color: '#f59e0b' },
}

/* ── Plan definitions for upgrade cards ── */
const PLAN_DEFS = [
  {
    key: 'free',
    name: '免费版',
    price: 0,
    color: '#64748b',
    features: [
      '100 次/月 API 调用',
      '10,000 Token/月',
      '1 个工作流',
      '社区支持',
    ],
  },
  {
    key: 'pro',
    name: '专业版',
    price: 299,
    color: '#6366f1',
    features: [
      '10,000 次/月 API 调用',
      '1,000,000 Token/月',
      '无限工作流',
      '优先技术支持',
      '高级模型访问',
    ],
  },
  {
    key: 'enterprise',
    name: '企业版',
    price: 999,
    color: '#f59e0b',
    features: [
      '无限 API 调用',
      '无限 Token',
      '无限工作流',
      '专属客户经理',
      '私有化部署',
      'SLA 保障',
    ],
  },
]

const DURATION_OPTIONS = [
  { label: '1 个月', value: 1 },
  { label: '3 个月 (9折)', value: 3, discount: 0.9 },
  { label: '6 个月 (8折)', value: 6, discount: 0.8 },
  { label: '12 个月 (7折)', value: 12, discount: 0.7 },
]

const PAYMENT_METHODS = [
  { label: '微信支付', value: 'wechat', icon: '💳' },
  { label: '支付宝', value: 'alipay', icon: '💰' },
  { label: '银行转账', value: 'bank_transfer', icon: '🏦' },
]

const ORDER_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待支付', color: 'orange' },
  paid: { label: '已支付', color: 'green' },
  cancelled: { label: '已取消', color: 'default' },
  refunded: { label: '已退款', color: 'red' },
}

function UsageBillingTab() {
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [plan, setPlan] = useState<PlanInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [orders, setOrders] = useState<PaymentOrder[]>([])
  const [ordersLoading, setOrdersLoading] = useState(false)

  /* Payment modal state */
  const [payModalOpen, setPayModalOpen] = useState(false)
  const [payingPlan, setPayingPlan] = useState<typeof PLAN_DEFS[0] | null>(null)
  const [payMonths, setPayMonths] = useState(1)
  const [payMethod, setPayMethod] = useState('wechat')
  const [payProcessing, setPayProcessing] = useState(false)

  const loadData = useCallback(() => {
    setLoading(true)
    Promise.all([getUsage(), getPlan()])
      .then(([u, p]) => {
        setUsage(u)
        setPlan(p)
      })
      .catch((err) => {
        message.error(`加载用量数据失败: ${err.message}`)
      })
      .finally(() => setLoading(false))
  }, [])

  const loadOrders = useCallback(() => {
    setOrdersLoading(true)
    getOrders()
      .then(setOrders)
      .catch((err) => {
        message.error(`加载订单列表失败: ${err.message}`)
      })
      .finally(() => setOrdersLoading(false))
  }, [])

  useEffect(() => {
    loadData()
    loadOrders()
  }, [loadData, loadOrders])

  /* Calculate total price */
  const calcTotal = (): number => {
    if (!payingPlan) return 0
    const dur = DURATION_OPTIONS.find((d) => d.value === payMonths)
    const discount = dur?.discount ?? 1
    return Math.round(payingPlan.price * payMonths * discount)
  }

  /* Open upgrade modal */
  const openUpgradeModal = (planDef: typeof PLAN_DEFS[0]) => {
    setPayingPlan(planDef)
    setPayMonths(1)
    setPayMethod('wechat')
    setPayModalOpen(true)
  }

  /* Process payment */
  const handlePay = async () => {
    if (!payingPlan) return
    setPayProcessing(true)
    try {
      // Step 1: Create order
      const order = await createOrder({
        plan: payingPlan.key,
        months: payMonths,
        payment_method: payMethod,
      })

      // Step 2: Simulate payment
      const result = await payOrder(order.order_id, {
        payment_method: payMethod,
      })

      if (result.status === 'paid') {
        message.success('支付成功！套餐已升级')
        setPayModalOpen(false)
        // Refresh data
        loadData()
        loadOrders()
      } else {
        message.warning(result.message || '支付处理中，请稍后查看')
      }
    } catch (err) {
      message.error(`支付失败: ${(err as Error).message}`)
    } finally {
      setPayProcessing(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 24, color: '#6366f1' }} />} />
      </div>
    )
  }

  if (!plan || !usage) {
    return (
      <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
        暂无数据
      </div>
    )
  }

  const callsPercent =
    plan.monthly_calls_limit > 0
      ? Math.round((plan.monthly_calls_used / plan.monthly_calls_limit) * 100)
      : 0
  const tokensPercent =
    plan.monthly_tokens_limit > 0
      ? Math.round((plan.monthly_tokens_used / plan.monthly_tokens_limit) * 100)
      : 0

  const planMeta = PLAN_LABELS[plan.plan] || PLAN_LABELS.free
  const currentPlanIndex = PLAN_DEFS.findIndex((p) => p.key === plan.plan)

  return (
    <>
      <GlassCard hoverable={false}>
        <h3 style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 600, marginBottom: 20 }}>
          用量与计费
        </h3>

        {/* Current Plan */}
        <div
          style={{
            padding: 16,
            borderRadius: 10,
            background: 'rgba(99,102,241,0.08)',
            border: '1px solid rgba(99,102,241,0.2)',
            marginBottom: 24,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>当前套餐</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <CrownOutlined style={{ fontSize: 20, color: planMeta.color }} />
              <span style={{ fontSize: 18, fontWeight: 700, color: '#e2e8f0' }}>
                {planMeta.label}
              </span>
            </div>
          </div>
        </div>

        {/* Plan Comparison Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 16,
            marginBottom: 24,
          }}
        >
          {PLAN_DEFS.map((pd, idx) => {
            const isCurrent = pd.key === plan.plan
            const isLower = idx <= currentPlanIndex

            return (
              <div
                key={pd.key}
                style={{
                  padding: 20,
                  borderRadius: 12,
                  background: isCurrent
                    ? `${pd.color}12`
                    : 'rgba(0,0,0,0.15)',
                  border: isCurrent
                    ? `2px solid ${pd.color}66`
                    : '1px solid rgba(148,163,184,0.1)',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'all 0.2s',
                }}
              >
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 700,
                    color: pd.color,
                    marginBottom: 8,
                  }}
                >
                  {pd.name}
                  {isCurrent && (
                    <Tag
                      color="processing"
                      style={{ marginLeft: 8, borderRadius: 4, fontSize: 11 }}
                    >
                      当前
                    </Tag>
                  )}
                </div>
                <div style={{ fontSize: 28, fontWeight: 800, color: '#e2e8f0', marginBottom: 16 }}>
                  {pd.price === 0 ? '免费' : `¥${pd.price}`}
                  {pd.price > 0 && (
                    <span style={{ fontSize: 14, fontWeight: 400, color: '#64748b' }}>
                      /月
                    </span>
                  )}
                </div>
                <div style={{ flex: 1, marginBottom: 16 }}>
                  {pd.features.map((feat) => (
                    <div
                      key={feat}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginBottom: 8,
                        fontSize: 13,
                        color: '#cbd5e1',
                      }}
                    >
                      <CheckCircleOutlined
                        style={{ color: pd.color, fontSize: 12 }}
                      />
                      {feat}
                    </div>
                  ))}
                </div>
                {isCurrent ? (
                  <Button disabled block>
                    当前套餐
                  </Button>
                ) : isLower ? (
                  <Button disabled block style={{ opacity: 0.5 }}>
                    降级不可用
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    block
                    style={{
                      background: pd.color,
                      borderColor: pd.color,
                    }}
                    icon={<CrownOutlined />}
                    onClick={() => openUpgradeModal(pd)}
                  >
                    升级到{pd.name}
                  </Button>
                )}
              </div>
            )
          })}
        </div>

        {/* Usage Progress */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 500 }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ color: '#cbd5e1', fontSize: 14 }}>API 调用次数</span>
              <span style={{ color: '#94a3b8', fontSize: 13 }}>
                {plan.monthly_calls_used.toLocaleString()} / {plan.monthly_calls_limit.toLocaleString()}
              </span>
            </div>
            <Progress
              percent={callsPercent}
              strokeColor={callsPercent >= 80 ? '#ef4444' : { from: '#6366f1', to: '#8b5cf6' }}
              trailColor="rgba(148,163,184,0.1)"
              size="small"
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ color: '#cbd5e1', fontSize: 14 }}>Token 用量</span>
              <span style={{ color: '#94a3b8', fontSize: 13 }}>
                {plan.monthly_tokens_used.toLocaleString()} / {plan.monthly_tokens_limit.toLocaleString()}
              </span>
            </div>
            <Progress
              percent={tokensPercent}
              strokeColor={tokensPercent >= 80 ? '#ef4444' : { from: '#0ea5e9', to: '#06b6d4' }}
              trailColor="rgba(148,163,184,0.1)"
              size="small"
            />
          </div>
        </div>

        {/* Usage Details */}
        <div style={{ marginTop: 24, borderTop: '1px solid rgba(148,163,184,0.1)', paddingTop: 20 }}>
          <h4 style={{ color: '#cbd5e1', fontSize: 14, marginBottom: 12 }}>本月用量明细</h4>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
              gap: 12,
            }}
          >
            {[
              { label: '总调用', value: usage.monthly_calls },
              { label: '总 Token', value: usage.monthly_tokens },
              { label: '对话调用', value: usage.chat_calls },
              { label: 'MCP 调用', value: usage.mcp_calls },
              { label: 'RAG 调用', value: usage.rag_calls },
              { label: '对话 Token', value: usage.chat_tokens },
            ].map((item) => (
              <div
                key={item.label}
                style={{
                  padding: 12,
                  borderRadius: 8,
                  background: 'rgba(0,0,0,0.15)',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: 18, fontWeight: 700, color: '#e2e8f0' }}>
                  {item.value.toLocaleString()}
                </div>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{item.label}</div>
              </div>
            ))}
          </div>
        </div>
      </GlassCard>

      {/* Order History */}
      <GlassCard hoverable={false} style={{ marginTop: 16 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 16,
          }}
        >
          <h3 style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 600, margin: 0 }}>
            <WalletOutlined style={{ marginRight: 8 }} />
            订单记录
          </h3>
        </div>
        <Table
          dataSource={orders}
          rowKey="id"
          pagination={{ pageSize: 5 }}
          size="small"
          loading={ordersLoading}
          locale={{
            emptyText: <span style={{ color: '#64748b' }}>暂无订单</span>,
          }}
          columns={[
            {
              title: '订单号',
              dataIndex: 'order_no',
              key: 'order_no',
              render: (val: string) => (
                <code style={{ fontSize: 12, color: '#94a3b8' }}>{val}</code>
              ),
            },
            {
              title: '套餐',
              dataIndex: 'plan',
              key: 'plan',
              render: (val: string) => {
                const pm = PLAN_LABELS[val] || { label: val, color: '#64748b' }
                return (
                  <Tag
                    style={{
                      borderRadius: 4,
                      color: pm.color,
                      borderColor: `${pm.color}44`,
                      background: `${pm.color}11`,
                    }}
                  >
                    {pm.label}
                  </Tag>
                )
              },
            },
            {
              title: '时长',
              dataIndex: 'months',
              key: 'months',
              width: 80,
              render: (val: number) => `${val} 个月`,
            },
            {
              title: '金额',
              dataIndex: 'amount',
              key: 'amount',
              width: 100,
              render: (val: number, record: PaymentOrder) => (
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>
                  {record.currency === 'CNY' ? '¥' : '$'}{val.toFixed(2)}
                </span>
              ),
            },
            {
              title: '支付方式',
              dataIndex: 'payment_method',
              key: 'payment_method',
              width: 100,
              render: (val: string | null) => {
                if (!val) return <span style={{ color: '#64748b' }}>-</span>
                const methodMap: Record<string, string> = {
                  wechat: '微信支付',
                  alipay: '支付宝',
                  bank_transfer: '银行转账',
                }
                return methodMap[val] || val
              },
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              width: 90,
              render: (val: string) => {
                const st = ORDER_STATUS_MAP[val] || { label: val, color: 'default' }
                return (
                  <Tag color={st.color} style={{ borderRadius: 4 }}>
                    {st.label}
                  </Tag>
                )
              },
            },
            {
              title: '创建时间',
              dataIndex: 'created_at',
              key: 'created_at',
              render: (val: string) =>
                val ? new Date(val).toLocaleString('zh-CN') : '-',
            },
          ]}
        />
      </GlassCard>

      {/* Payment Modal */}
      <Modal
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <CrownOutlined style={{ color: payingPlan?.color }} />
            升级到{payingPlan?.name}
          </span>
        }
        open={payModalOpen}
        onCancel={() => setPayModalOpen(false)}
        footer={null}
        width={480}
      >
        {payingPlan && (
          <div style={{ padding: '12px 0' }}>
            {/* Plan info */}
            <div
              style={{
                padding: 16,
                borderRadius: 10,
                background: `${payingPlan.color}08`,
                border: `1px solid ${payingPlan.color}22`,
                marginBottom: 20,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0' }}>
                  {payingPlan.name}
                </span>
                <span style={{ fontSize: 20, fontWeight: 700, color: payingPlan.color }}>
                  ¥{payingPlan.price}/月
                </span>
              </div>
            </div>

            {/* Duration select */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 14, color: '#cbd5e1', marginBottom: 8, fontWeight: 500 }}>
                订阅时长
              </div>
              <Select
                value={payMonths}
                onChange={setPayMonths}
                style={{ width: '100%' }}
                options={DURATION_OPTIONS.map((d) => ({
                  label: d.label,
                  value: d.value,
                }))}
              />
            </div>

            {/* Total */}
            <div
              style={{
                padding: 16,
                borderRadius: 10,
                background: 'rgba(0,0,0,0.15)',
                marginBottom: 20,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span style={{ fontSize: 14, color: '#94a3b8' }}>合计</span>
              <span style={{ fontSize: 28, fontWeight: 800, color: '#e2e8f0' }}>
                ¥{calcTotal()}
              </span>
            </div>

            {/* Payment method */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 14, color: '#cbd5e1', marginBottom: 10, fontWeight: 500 }}>
                支付方式
              </div>
              <Radio.Group
                value={payMethod}
                onChange={(e) => setPayMethod(e.target.value)}
                style={{ width: '100%' }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {PAYMENT_METHODS.map((pm) => (
                    <Radio
                      key={pm.value}
                      value={pm.value}
                      style={{
                        padding: '10px 14px',
                        borderRadius: 8,
                        background:
                          payMethod === pm.value
                            ? 'rgba(99,102,241,0.1)'
                            : 'rgba(0,0,0,0.1)',
                        border:
                          payMethod === pm.value
                            ? '1px solid rgba(99,102,241,0.3)'
                            : '1px solid rgba(148,163,184,0.1)',
                        margin: 0,
                        width: '100%',
                        transition: 'all 0.2s',
                      }}
                    >
                      <span style={{ fontSize: 14, color: '#e2e8f0' }}>
                        {pm.icon} {pm.label}
                      </span>
                    </Radio>
                  ))}
                </div>
              </Radio.Group>
            </div>

            {/* Pay button */}
            <Button
              type="primary"
              block
              size="large"
              loading={payProcessing}
              onClick={handlePay}
              style={{
                height: 48,
                fontSize: 16,
                fontWeight: 600,
                borderRadius: 10,
                background: payingPlan.color,
                borderColor: payingPlan.color,
              }}
            >
              确认支付 ¥{calcTotal()}
            </Button>

            {/* Note */}
            <div
              style={{
                marginTop: 16,
                padding: 12,
                borderRadius: 8,
                background: 'rgba(234,179,8,0.06)',
                border: '1px solid rgba(234,179,8,0.15)',
                fontSize: 12,
                color: '#94a3b8',
                textAlign: 'center',
                lineHeight: 1.8,
              }}
            >
              注：当前为模拟支付，实际支付功能将在后续版本开放。
            </div>
          </div>
        )}
      </Modal>
    </>
  )
}

function ChannelsTab() {
  const [channels, setChannels] = useState<ChannelStatus[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    getChannelStatus()
      .then(setChannels)
      .catch((err) => {
        message.error(`加载渠道状态失败: ${err.message}`)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 24, color: '#6366f1' }} />} />
      </div>
    )
  }

  return (
    <GlassCard hoverable={false}>
      <h3 style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 600, marginBottom: 20 }}>
        渠道管理
      </h3>

      {channels.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>
          暂无渠道配置
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {channels.map((ch) => (
            <div
              key={ch.name}
              style={{
                padding: 16,
                borderRadius: 10,
                background: 'rgba(0,0,0,0.15)',
                border: '1px solid rgba(148,163,184,0.1)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <LinkOutlined style={{ fontSize: 18, color: '#6366f1' }} />
                  <span style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0' }}>
                    {ch.display_name}
                  </span>
                </div>
                {ch.configured ? (
                  <Tag
                    icon={<CheckCircleOutlined />}
                    color="success"
                    style={{ borderRadius: 4 }}
                  >
                    已配置
                  </Tag>
                ) : (
                  <Tag
                    icon={<CloseCircleOutlined />}
                    color="default"
                    style={{ borderRadius: 4 }}
                  >
                    未配置
                  </Tag>
                )}
              </div>

              <div style={{ maxWidth: 500 }}>
                {ch.name === 'wechat_work' && (
                  <div style={{ color: '#94a3b8', fontSize: 13, lineHeight: 2 }}>
                    <div style={{ color: '#cbd5e1', fontWeight: 600, marginBottom: 8 }}>
                      渠道配置需要在服务器 .env 文件中设置以下环境变量：
                    </div>
                    <code style={{ display: 'block', padding: 12, borderRadius: 8, background: 'rgba(0,0,0,0.3)', fontSize: 12, lineHeight: 1.8 }}>
                      WECHAT_WORK_CORP_ID=你的企业微信CorpID<br />
                      WECHAT_WORK_CORP_SECRET=你的企业微信CorpSecret<br />
                      WECHAT_WORK_TOKEN=回调Token<br />
                      WECHAT_WORK_AES_KEY=回调EncodingAESKey
                    </code>
                  </div>
                )}
                {ch.name === 'dingtalk' && (
                  <div style={{ color: '#94a3b8', fontSize: 13, lineHeight: 2 }}>
                    <div style={{ color: '#cbd5e1', fontWeight: 600, marginBottom: 8 }}>
                      渠道配置需要在服务器 .env 文件中设置以下环境变量：
                    </div>
                    <code style={{ display: 'block', padding: 12, borderRadius: 8, background: 'rgba(0,0,0,0.3)', fontSize: 12, lineHeight: 1.8 }}>
                      DINGTALK_APP_KEY=你的钉钉AppKey<br />
                      DINGTALK_APP_SECRET=你的钉钉AppSecret<br />
                      DINGTALK_SIGN_KEY=机器人安全设置签名密钥
                    </code>
                  </div>
                )}
                {ch.name !== 'wechat_work' && ch.name !== 'dingtalk' && (
                  <div style={{ color: '#64748b', fontSize: 13 }}>
                    请在服务端环境变量中配置此渠道的凭据。
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  )
}

function ApiKeysTab() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState<string | null>(null)

  const loadKeys = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getApiKeys()
      setKeys(data)
    } catch (err) {
      message.error(`加载 API 密钥失败: ${err instanceof Error ? err.message : '未知错误'}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadKeys()
  }, [loadKeys])

  const handleCreate = async () => {
    if (!newKeyName.trim()) {
      message.warning('请输入密钥名称')
      return
    }
    try {
      const result = await createApiKey({ name: newKeyName.trim() })
      setCreatedKey(result.plain_key || result.key || '')
      setNewKeyName('')
      await loadKeys()
      message.success('API 密钥已创建，请立即复制保存')
    } catch (err) {
      message.error(`创建失败: ${err instanceof Error ? err.message : '未知错误'}`)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteApiKey(id)
      setKeys((prev) => prev.filter((k) => k.id !== id))
      message.success('已删除')
    } catch (err) {
      message.error(`删除失败: ${err instanceof Error ? err.message : '未知错误'}`)
    }
  }

  const handleRevoke = async (id: string) => {
    try {
      await revokeApiKey(id)
      await loadKeys()
      message.success('已吊销')
    } catch (err) {
      message.error(`吊销失败: ${err instanceof Error ? err.message : '未知错误'}`)
    }
  }

  return (
    <GlassCard hoverable={false}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <h3 style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 600, margin: 0 }}>
          API 密钥管理
        </h3>
        <Button type="primary" icon={<PlusOutlined />} size="small" onClick={() => setCreateOpen(true)}>
          添加密钥
        </Button>
      </div>

      {createdKey && (
        <div
          style={{
            padding: 12,
            marginBottom: 16,
            borderRadius: 8,
            background: 'rgba(34,197,94,0.1)',
            border: '1px solid rgba(34,197,94,0.3)',
          }}
        >
          <div style={{ fontSize: 13, color: '#22c55e', marginBottom: 8, fontWeight: 600 }}>
            密钥已创建，请立即复制保存（关闭后无法再次查看）：
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <code style={{ fontSize: 13, color: '#e2e8f0', wordBreak: 'break-all' }}>{createdKey}</code>
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => {
                navigator.clipboard.writeText(createdKey)
                message.success('已复制')
              }}
              style={{ color: '#22c55e' }}
            />
          </div>
          <Button
            type="text"
            size="small"
            onClick={() => setCreatedKey(null)}
            style={{ color: '#64748b', marginTop: 8 }}
          >
            关闭
          </Button>
        </div>
      )}

      <Table
        dataSource={keys}
        rowKey="id"
        pagination={false}
        size="small"
        loading={loading}
        columns={[
          { title: '名称', dataIndex: 'name', key: 'name' },
          {
            title: '密钥前缀',
            dataIndex: 'prefix',
            key: 'prefix',
            render: (prefix: string) => (
              <span style={{ fontFamily: 'monospace', color: '#94a3b8' }}>
                <EyeInvisibleOutlined style={{ marginRight: 6 }} />
                {prefix}...
              </span>
            ),
          },
          {
            title: '状态',
            dataIndex: 'is_active',
            key: 'is_active',
            width: 80,
            render: (active: boolean) =>
              active ? (
                <Tag color="success" style={{ borderRadius: 4 }}>有效</Tag>
              ) : (
                <Tag color="default" style={{ borderRadius: 4 }}>已吊销</Tag>
              ),
          },
          {
            title: '创建时间',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (val: string) => val ? new Date(val).toLocaleDateString('zh-CN') : '-',
          },
          {
            title: '最后使用',
            dataIndex: 'last_used_at',
            key: 'last_used_at',
            render: (val: string | null) => val ? new Date(val).toLocaleString('zh-CN') : '从未',
          },
          {
            title: '操作',
            key: 'action',
            width: 140,
            render: (_: unknown, record: ApiKeyItem) => (
              <div style={{ display: 'flex', gap: 4 }}>
                {record.is_active && (
                  <Popconfirm title="确认吊销此密钥？" onConfirm={() => handleRevoke(record.id)}>
                    <Button type="text" size="small" style={{ color: '#f59e0b', fontSize: 12 }}>
                      吊销
                    </Button>
                  </Popconfirm>
                )}
                <Popconfirm title="确认删除此密钥？" onConfirm={() => handleDelete(record.id)}>
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    style={{ color: '#ef4444' }}
                  />
                </Popconfirm>
              </div>
            ),
          },
        ]}
      />

      <Modal
        title="创建 API 密钥"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => { setCreateOpen(false); setNewKeyName('') }}
        okText="创建"
        cancelText="取消"
      >
        <div style={{ marginTop: 16 }}>
          <div style={{ marginBottom: 4, fontSize: 13, color: '#cbd5e1' }}>密钥名称</div>
          <Input
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            placeholder="例如：生产环境密钥"
          />
        </div>
      </Modal>
    </GlassCard>
  )
}

function TeamTab() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteForm] = Form.useForm()
  const [inviting, setInviting] = useState(false)
  const [invitedPassword, setInvitedPassword] = useState<string | null>(null)

  const loadUsers = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getUsers()
      setUsers(data)
    } catch (err) {
      message.error(`加载团队成员失败: ${err instanceof Error ? err.message : '未知错误'}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  const handleInvite = async () => {
    try {
      const values = await inviteForm.validateFields()
      setInviting(true)
      const result = await inviteUser(values)
      setUsers((prev) => [...prev, result])
      setInviteOpen(false)
      inviteForm.resetFields()
      // Show temp password (#40)
      const tempPassword = (result as User & { temp_password?: string }).temp_password
      if (tempPassword) {
        setInvitedPassword(tempPassword)
      } else {
        message.success(`已邀请用户「${values.username}」`)
      }
    } catch (err) {
      if (err instanceof Error) {
        message.error(`邀请失败: ${err.message}`)
      }
    } finally {
      setInviting(false)
    }
  }

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await changeRole(userId, { role: newRole })
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u)),
      )
      message.success('角色已更新')
    } catch (err) {
      message.error(`更新失败: ${err instanceof Error ? err.message : '未知错误'}`)
    }
  }

  const handleDelete = async (userId: string) => {
    try {
      await deleteUser(userId)
      setUsers((prev) => prev.filter((u) => u.id !== userId))
      message.success('已删除')
    } catch (err) {
      message.error(`删除失败: ${err instanceof Error ? err.message : '未知错误'}`)
    }
  }

  return (
    <GlassCard hoverable={false}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <h3 style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 600, margin: 0 }}>
          团队成员
        </h3>
        <Button type="primary" icon={<PlusOutlined />} size="small" onClick={() => setInviteOpen(true)}>
          邀请成员
        </Button>
      </div>
      <Table
        dataSource={users}
        rowKey="id"
        pagination={false}
        size="small"
        loading={loading}
        columns={[
          { title: '用户名', dataIndex: 'username', key: 'username' },
          { title: '邮箱', dataIndex: 'email', key: 'email' },
          {
            title: '角色',
            dataIndex: 'role',
            key: 'role',
            render: (role: string, record: User) => (
              <Select
                value={role}
                size="small"
                style={{ width: 100 }}
                onChange={(val) => handleRoleChange(record.id, val)}
                options={[
                  { label: '管理员', value: 'admin' },
                  { label: '用户', value: 'user' },
                ]}
              />
            ),
          },
          {
            title: '状态',
            dataIndex: 'is_active',
            key: 'is_active',
            width: 80,
            render: (active: boolean) =>
              active ? (
                <Tag color="success" style={{ borderRadius: 4 }}>活跃</Tag>
              ) : (
                <Tag color="default" style={{ borderRadius: 4 }}>禁用</Tag>
              ),
          },
          {
            title: '操作',
            key: 'action',
            width: 80,
            render: (_: unknown, record: User) => (
              <Popconfirm
                title="确认删除此用户？"
                onConfirm={() => handleDelete(record.id)}
              >
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  style={{ color: '#ef4444' }}
                />
              </Popconfirm>
            ),
          },
        ]}
      />

      {/* Invite Modal */}
      <Modal
        title="邀请成员"
        open={inviteOpen}
        onOk={handleInvite}
        onCancel={() => { setInviteOpen(false); inviteForm.resetFields() }}
        okText="邀请"
        cancelText="取消"
        confirmLoading={inviting}
      >
        <Form form={inviteForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="新成员的用户名" />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}>
            <Input placeholder="新成员的邮箱" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]} initialValue="user">
            <Select
              options={[
                { label: '管理员', value: 'admin' },
                { label: '用户', value: 'user' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Temp Password Modal (#40) */}
      <Modal
        title="邀请成功"
        open={!!invitedPassword}
        onOk={() => setInvitedPassword(null)}
        onCancel={() => setInvitedPassword(null)}
        okText="确定"
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        <div style={{ marginTop: 12 }}>
          <p style={{ color: '#cbd5e1', marginBottom: 12 }}>
            用户已创建，请将以下临时密码发送给该成员，首次登录后需修改密码：
          </p>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: 12,
              borderRadius: 8,
              background: 'rgba(34,197,94,0.1)',
              border: '1px solid rgba(34,197,94,0.3)',
            }}
          >
            <code style={{ fontSize: 16, fontWeight: 600, color: '#e2e8f0', flex: 1, wordBreak: 'break-all' }}>
              {invitedPassword}
            </code>
            <Button
              type="text"
              icon={<CopyOutlined />}
              onClick={() => {
                if (invitedPassword) {
                  navigator.clipboard.writeText(invitedPassword)
                  message.success('已复制到剪贴板')
                }
              }}
              style={{ color: '#22c55e' }}
            />
          </div>
        </div>
      </Modal>
    </GlassCard>
  )
}

export default function SettingsPage() {
  const [models, setModels] = useState<SystemModel[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [defaultModel, setDefaultModel] = useState('deepseek-chat')
  const [defaultTemperature, setDefaultTemperature] = useState(0.7)
  const [streamEnabled, setStreamEnabled] = useState(true)
  const [contentFilterEnabled, setContentFilterEnabled] = useState(true)
  const [platformName, setPlatformName] = useState('BridgeAI')
  const [language, setLanguage] = useState('zh')
  const [notificationsEnabled, setNotificationsEnabled] = useState(true)
  const [auditLogEnabled, setAuditLogEnabled] = useState(true)
  const [saving, setSaving] = useState(false)
  const { t, i18n } = useTranslation()

  useEffect(() => {
    setModelsLoading(true)
    Promise.all([getSystemModels(), getSystemSettings()])
      .then(([modelsData, settingsData]) => {
        setModels(modelsData)
        // Apply saved settings or fallback to defaults
        if (settingsData.default_model) {
          setDefaultModel(settingsData.default_model)
        } else {
          const firstAvailable = modelsData.find((m) => m.available)
          if (firstAvailable) setDefaultModel(firstAvailable.id)
        }
        if (settingsData.default_temperature != null) setDefaultTemperature(settingsData.default_temperature)
        if (settingsData.stream_enabled != null) setStreamEnabled(settingsData.stream_enabled)
        if (settingsData.content_filter_enabled != null) setContentFilterEnabled(settingsData.content_filter_enabled)
        if (settingsData.platform_name) setPlatformName(settingsData.platform_name)
        if (settingsData.language) setLanguage(settingsData.language)
        if (settingsData.notifications_enabled != null) setNotificationsEnabled(settingsData.notifications_enabled)
        if (settingsData.audit_log_enabled != null) setAuditLogEnabled(settingsData.audit_log_enabled)
      })
      .catch((err) => {
        message.error(`加载配置失败: ${err.message}`)
      })
      .finally(() => setModelsLoading(false))
  }, [])

  const handleModelConfigSave = async () => {
    setSaving(true)
    try {
      await updateSystemSettings({
        default_model: defaultModel,
        default_temperature: defaultTemperature,
        stream_enabled: streamEnabled,
        content_filter_enabled: contentFilterEnabled,
      })
      message.success('模型配置已保存')
    } catch (err) {
      message.error(`保存失败: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleGeneralSave = async () => {
    setSaving(true)
    try {
      await updateSystemSettings({
        platform_name: platformName,
        language,
        notifications_enabled: notificationsEnabled,
        audit_log_enabled: auditLogEnabled,
      })
      message.success(t('settings.generalSaved'))
    } catch (err) {
      message.error(`保存失败: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const availableModels = models.filter((m) => m.available)

  return (
    <div className="animate-fade-in">
      <h2 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', marginBottom: 24 }}>
        {t('settings.title')}
      </h2>

      <Tabs
        tabPosition="left"
        style={{ minHeight: 500 }}
        items={[
          {
            key: 'model',
            label: (
              <span>
                <RobotOutlined style={{ marginRight: 8 }} />
                {t('settings.modelConfig')}
              </span>
            ),
            children: (
              <GlassCard hoverable={false}>
                <h3 style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 600, marginBottom: 20 }}>
                  默认模型配置
                </h3>

                {/* Model Status Table */}
                <div style={{ marginBottom: 24 }}>
                  <h4 style={{ color: '#cbd5e1', fontSize: 14, marginBottom: 12 }}>可用模型</h4>
                  {modelsLoading ? (
                    <Spin indicator={<LoadingOutlined style={{ fontSize: 24, color: '#6366f1' }} />} />
                  ) : (
                    <Table
                      dataSource={models}
                      rowKey="id"
                      pagination={false}
                      size="small"
                      columns={[
                        { title: '模型', dataIndex: 'name', key: 'name' },
                        { title: 'ID', dataIndex: 'id', key: 'id', render: (id: string) => (
                          <code style={{ fontSize: 12, color: '#94a3b8' }}>{id}</code>
                        )},
                        { title: '提供商', dataIndex: 'provider', key: 'provider', render: (p: string) => (
                          <Tag style={{ textTransform: 'capitalize' }}>{p}</Tag>
                        )},
                        {
                          title: '状态',
                          dataIndex: 'available',
                          key: 'available',
                          render: (available: boolean) =>
                            available ? (
                              <span style={{ color: '#22c55e' }}>
                                <CheckCircleOutlined style={{ marginRight: 4 }} />
                                可用
                              </span>
                            ) : (
                              <span style={{ color: '#ef4444' }}>
                                <CloseCircleOutlined style={{ marginRight: 4 }} />
                                未配置
                              </span>
                            ),
                        },
                      ]}
                    />
                  )}
                </div>

                <Form layout="vertical" style={{ maxWidth: 500 }}>
                  <Form.Item label={<span style={{ color: '#cbd5e1' }}>默认模型</span>}>
                    <Select
                      value={defaultModel}
                      onChange={setDefaultModel}
                      loading={modelsLoading}
                      options={availableModels.map((m) => ({
                        label: `${m.name} (${m.provider})`,
                        value: m.id,
                      }))}
                    />
                  </Form.Item>
                  <Form.Item label={<span style={{ color: '#cbd5e1' }}>默认温度</span>}>
                    <Input type="number" value={defaultTemperature} onChange={(e) => setDefaultTemperature(Number(e.target.value))} step="0.1" min="0" max="2" />
                  </Form.Item>
                  <Form.Item label={<span style={{ color: '#cbd5e1' }}>启用流式输出</span>}>
                    <Switch checked={streamEnabled} onChange={setStreamEnabled} />
                  </Form.Item>
                  <Form.Item label={<span style={{ color: '#cbd5e1' }}>启用内容过滤</span>}>
                    <Switch checked={contentFilterEnabled} onChange={setContentFilterEnabled} />
                  </Form.Item>
                  <Button type="primary" icon={<SaveOutlined />} onClick={handleModelConfigSave} loading={saving}>
                    保存配置
                  </Button>
                </Form>
              </GlassCard>
            ),
          },
          {
            key: 'apikeys',
            label: (
              <span>
                <KeyOutlined style={{ marginRight: 8 }} />
                {t('settings.apiKeys')}
              </span>
            ),
            children: <ApiKeysTab />,
          },
          {
            key: 'billing',
            label: (
              <span>
                <DollarOutlined style={{ marginRight: 8 }} />
                {t('settings.billing')}
              </span>
            ),
            children: <UsageBillingTab />,
          },
          {
            key: 'channels',
            label: (
              <span>
                <LinkOutlined style={{ marginRight: 8 }} />
                {t('settings.channels')}
              </span>
            ),
            children: <ChannelsTab />,
          },
          {
            key: 'team',
            label: (
              <span>
                <TeamOutlined style={{ marginRight: 8 }} />
                {t('settings.team')}
              </span>
            ),
            children: <TeamTab />,
          },
          {
            key: 'general',
            label: (
              <span>
                <SettingOutlined style={{ marginRight: 8 }} />
                {t('settings.general')}
              </span>
            ),
            children: (
              <GlassCard hoverable={false}>
                <h3 style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 600, marginBottom: 20 }}>
                  {t('settings.generalSettings')}
                </h3>
                <Form layout="vertical" style={{ maxWidth: 500 }}>
                  <Form.Item label={<span style={{ color: '#cbd5e1' }}>{t('settings.platformName')}</span>}>
                    <Input value={platformName} onChange={(e) => setPlatformName(e.target.value)} />
                  </Form.Item>
                  <Form.Item label={<span style={{ color: '#cbd5e1' }}>{t('settings.language')}</span>}>
                    <Select
                      value={language}
                      onChange={(val) => {
                        setLanguage(val)
                        i18n.changeLanguage(val)
                        localStorage.setItem('bridgeai-lang', val)
                      }}
                      options={[
                        { label: t('settings.langZh'), value: 'zh' },
                        { label: t('settings.langEn'), value: 'en' },
                      ]}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                  <Form.Item label={<span style={{ color: '#cbd5e1' }}>{t('settings.enableNotifications')}</span>}>
                    <Switch checked={notificationsEnabled} onChange={setNotificationsEnabled} />
                  </Form.Item>
                  <Form.Item label={<span style={{ color: '#cbd5e1' }}>{t('settings.enableAuditLog')}</span>}>
                    <Switch checked={auditLogEnabled} onChange={setAuditLogEnabled} />
                  </Form.Item>
                  <Button type="primary" icon={<SaveOutlined />} onClick={handleGeneralSave} loading={saving}>
                    {t('common.saveSettings')}
                  </Button>
                </Form>
              </GlassCard>
            ),
          },
        ]}
      />
    </div>
  )
}
