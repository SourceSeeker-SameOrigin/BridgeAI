import { useState, useEffect, useCallback } from 'react'
import { Table, Select, DatePicker, Tag, message, Space, Button } from 'antd'
import {
  FileSearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import GlassCard from '../../components/GlassCard'
import { getAuditLogs } from '../../api/audit'
import type { AuditLogItem, AuditLogFilters } from '../../api/audit'

const { RangePicker } = DatePicker

const TYPE_COLORS: Record<string, string> = {
  chat: 'blue',
  mcp: 'purple',
  plugin: 'orange',
  rag: 'green',
}

export default function AuditLogPage() {
  const { t } = useTranslation()
  const [data, setData] = useState<AuditLogItem[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [filters, setFilters] = useState<AuditLogFilters>({})
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)

  const TYPE_OPTIONS = [
    { label: t('audit.allTypes'), value: '' },
    { label: t('audit.typeChat'), value: 'chat' },
    { label: t('audit.typeMcp'), value: 'mcp' },
    { label: t('audit.typePlugin'), value: 'plugin' },
    { label: t('audit.typeRag'), value: 'rag' },
  ]

  const STATUS_OPTIONS = [
    { label: t('audit.allStatus'), value: '' },
    { label: t('audit.statusSuccess'), value: 'success' },
    { label: t('audit.statusError'), value: 'error' },
  ]

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const appliedFilters: AuditLogFilters = { ...filters }
      if (dateRange && dateRange[0]) {
        appliedFilters.start_date = dateRange[0].startOf('day').toISOString()
      }
      if (dateRange && dateRange[1]) {
        appliedFilters.end_date = dateRange[1].endOf('day').toISOString()
      }
      const result = await getAuditLogs(page, pageSize, appliedFilters)
      setData(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(`${t('audit.loadFailed')}: ${err instanceof Error ? err.message : t('common.unknownError')}`)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, filters, dateRange, t])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleTypeChange = (value: string) => {
    setPage(1)
    setFilters((prev) => ({ ...prev, log_type: value || undefined }))
  }

  const handleStatusChange = (value: string) => {
    setPage(1)
    setFilters((prev) => ({ ...prev, status: value || undefined }))
  }

  const handleDateChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    setPage(1)
    setDateRange(dates)
  }

  const columns: ColumnsType<AuditLogItem> = [
    {
      title: t('audit.colTime'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (val: string | null) =>
        val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: t('audit.colType'),
      dataIndex: 'log_type',
      key: 'log_type',
      width: 90,
      render: (val: string) => (
        <Tag color={TYPE_COLORS[val] || 'default'} style={{ borderRadius: 4 }}>
          {val}
        </Tag>
      ),
    },
    {
      title: t('audit.colAction'),
      dataIndex: 'action',
      key: 'action',
      width: 200,
      ellipsis: true,
    },
    {
      title: t('audit.colUser'),
      dataIndex: 'user_id',
      key: 'user_id',
      width: 120,
      ellipsis: true,
      render: (val: string | null) =>
        val ? <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{val.slice(0, 8)}...</span> : '-',
    },
    {
      title: t('audit.colStatus'),
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (val: string) =>
        val === 'success' ? (
          <Tag color="success" style={{ borderRadius: 4 }}>{t('audit.statusSuccess')}</Tag>
        ) : (
          <Tag color="error" style={{ borderRadius: 4 }}>{t('audit.statusError')}</Tag>
        ),
    },
    {
      title: t('audit.colDuration'),
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 90,
      render: (val: number | null) => (val != null ? `${val}ms` : '-'),
    },
    {
      title: t('audit.colModel'),
      dataIndex: 'model_used',
      key: 'model_used',
      width: 130,
      ellipsis: true,
      render: (val: string | null) =>
        val ? (
          <code style={{ fontSize: 12, color: '#94a3b8' }}>{val}</code>
        ) : (
          '-'
        ),
    },
  ]

  const expandedRowRender = (record: AuditLogItem) => (
    <div style={{ padding: '8px 0' }}>
      {record.error_message && (
        <div style={{ marginBottom: 8 }}>
          <strong style={{ color: '#ef4444' }}>{t('audit.errorMessage')}: </strong>
          <span style={{ color: '#f87171' }}>{record.error_message}</span>
        </div>
      )}
      {record.tokens_in != null && (
        <div style={{ marginBottom: 4, color: '#94a3b8', fontSize: 13 }}>
          {t('audit.inputTokens')}: {record.tokens_in} | {t('audit.outputTokens')}: {record.tokens_out ?? 0}
        </div>
      )}
      {record.request_payload && (
        <div style={{ marginBottom: 4 }}>
          <strong style={{ color: '#cbd5e1', fontSize: 12 }}>{t('audit.request')}: </strong>
          <pre
            style={{
              fontSize: 12,
              color: '#94a3b8',
              background: 'rgba(0,0,0,0.2)',
              padding: 8,
              borderRadius: 6,
              maxHeight: 200,
              overflow: 'auto',
              marginTop: 4,
            }}
          >
            {JSON.stringify(record.request_payload, null, 2)}
          </pre>
        </div>
      )}
      {record.response_payload && (
        <div>
          <strong style={{ color: '#cbd5e1', fontSize: 12 }}>{t('audit.response')}: </strong>
          <pre
            style={{
              fontSize: 12,
              color: '#94a3b8',
              background: 'rgba(0,0,0,0.2)',
              padding: 8,
              borderRadius: 6,
              maxHeight: 200,
              overflow: 'auto',
              marginTop: 4,
            }}
          >
            {JSON.stringify(record.response_payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )

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
          <FileSearchOutlined style={{ marginRight: 8 }} />
          {t('audit.title')}
        </h2>
        <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
          {t('common.refresh')}
        </Button>
      </div>

      <GlassCard hoverable={false} style={{ marginBottom: 16 }}>
        <Space wrap size={12}>
          <Select
            value={filters.log_type || ''}
            onChange={handleTypeChange}
            options={TYPE_OPTIONS}
            style={{ width: 130 }}
            placeholder={t('audit.logTypePlaceholder')}
          />
          <Select
            value={filters.status || ''}
            onChange={handleStatusChange}
            options={STATUS_OPTIONS}
            style={{ width: 130 }}
            placeholder={t('audit.statusPlaceholder')}
          />
          <RangePicker
            value={dateRange as [Dayjs, Dayjs] | undefined}
            onChange={handleDateChange}
            style={{ width: 280 }}
            placeholder={[t('audit.startDate'), t('audit.endDate')]}
          />
        </Space>
      </GlassCard>

      <GlassCard hoverable={false}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          expandable={{
            expandedRowRender,
            rowExpandable: (record) =>
              !!(
                record.error_message ||
                record.request_payload ||
                record.response_payload ||
                record.tokens_in != null
              ),
          }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `${t}`,
            onChange: (p, s) => {
              setPage(p)
              setPageSize(s)
            },
          }}
        />
      </GlassCard>
    </div>
  )
}
