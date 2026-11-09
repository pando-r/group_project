import {
  ClockCircleOutlined,
  FileDoneOutlined,
  PlusOutlined,
  ReloadOutlined,
  TeamOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { Link, useNavigate } from 'react-router-dom'

import { apiErrorMessage, dashboardApi } from '../api/client'
import { RiskBadge } from '../components/Badges'
import { PageHeader, SectionCard } from '../components/Layout'
import { MetricCardView } from '../components/MetricCard'
import {
  formatDateTime,
  formatPercent,
  RISK_LABEL,
  severityTone,
  TONE_CLASS,
} from '../lib/format'
import type { AssessmentQueueItem } from '../types/domain'

const METRIC_ICONS = {
  patients: <TeamOutlined />,
  monthly: <FileDoneOutlined />,
  pending: <ClockCircleOutlined />,
  high_risk: <WarningOutlined />,
}

const queueColumns: ColumnsType<AssessmentQueueItem> = [
  {
    title: '患者',
    dataIndex: 'patient_name',
    key: 'patient',
    width: 160,
    render: (_, record) => (
      <div className="cell-stack">
        <strong className="cell-strong">{record.patient_name}</strong>
        <span className="cell-muted">{record.mrn}</span>
      </div>
    ),
  },
  {
    title: '评估病种',
    dataIndex: 'disease_name',
    key: 'disease',
    width: 150,
  },
  {
    title: '分级',
    dataIndex: 'severity_grade',
    key: 'severity',
    width: 120,
    render: (_, record) => (
      <RiskBadge tone={severityTone(record.severity_level)} label={record.severity_grade} />
    ),
  },
  {
    title: '风险',
    key: 'risk',
    width: 110,
    render: (_, record) => (
      <span className="risk-inline">
        <strong>{formatPercent(record.risk_percent)}</strong>
        <small>{RISK_LABEL[record.risk_tier]}</small>
      </span>
    ),
  },
  {
    title: '提交时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 150,
    render: (value: string) => <span className="tabular">{formatDateTime(value)}</span>,
  },
  {
    title: '',
    key: 'action',
    width: 72,
    align: 'right',
    render: (_, record) => (
      <Link to={`/assessments/${record.id}`} className="table-action" onClick={(event) => event.stopPropagation()}>
        复核
      </Link>
    ),
  },
]

export function DashboardPage() {
  const navigate = useNavigate()
  const dashboard = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.get,
  })

  const data = dashboard.data

  return (
    <div className="page">
      <PageHeader
        title="临床工作台"
        description={dayjs().format('YYYY年M月D日 dddd') + ' · 今日需优先处理待确认评估'}
        extra={
          <>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => void dashboard.refetch()}
              loading={dashboard.isRefetching}
            >
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/assessments/new')}>
              新建评估
            </Button>
          </>
        }
      />

      {dashboard.isError ? (
        <SectionCard>
          <div className="inline-error">
            <strong>工作台数据加载失败</strong>
            <p>{apiErrorMessage(dashboard.error)}</p>
            <Button onClick={() => void dashboard.refetch()}>重试</Button>
          </div>
        </SectionCard>
      ) : null}

      {!dashboard.isError && !data ? (
        <div className="metrics-grid" aria-busy="true">
          {[0, 1, 2, 3].map((item) => (
            <div className="metric-card metric-skeleton" key={item}>
              <span />
              <span />
            </div>
          ))}
        </div>
      ) : null}

      {data ? (
        <>
          <div className="metrics-grid">
            {data.metrics.map((metric) => (
              <MetricCardView
                key={metric.key}
                label={metric.label}
                value={metric.value}
                unit={metric.unit}
                hint={metric.hint}
                icon={METRIC_ICONS[metric.key as keyof typeof METRIC_ICONS]}
                attention={metric.key === 'high_risk' && metric.value > 0}
              />
            ))}
          </div>

          <div className="dashboard-grid">
            <div className="dashboard-main">
              <SectionCard
                title="待确认评估"
                description="按提交时间倒序，仅显示最近 8 条。"
                extra={<Link to="/patients">查看全部患者</Link>}
                padded={false}
              >
                <Table<AssessmentQueueItem>
                  rowKey="id"
                  className="data-table"
                  columns={queueColumns}
                  dataSource={data.pending_queue}
                  pagination={false}
                  scroll={{ x: 760 }}
                  locale={{ emptyText: <div className="table-empty">暂无待确认评估</div> }}
                  onRow={(record) => ({
                    onClick: () => navigate(`/assessments/${record.id}`),
                    style: { cursor: 'pointer' },
                  })}
                />
              </SectionCard>

              <SectionCard
                title="最近活动"
                description="评估创建与医生签核会写入审计日志。"
              >
                {data.recent_activity.length === 0 ? (
                  <div className="table-empty">暂无活动记录</div>
                ) : (
                  <ol className="activity-list">
                    {data.recent_activity.map((item) => (
                      <li key={`${item.assessment_id}-${item.created_at}`}>
                        <Link to={`/assessments/${item.assessment_id}`} className="activity-row">
                          <span className="activity-node" aria-hidden="true" />
                          <span className="activity-body">
                            <span className="activity-title">
                              <strong>{item.patient_name}</strong>
                              <span>{item.action}</span>
                            </span>
                            <span className="activity-detail">
                              {item.detail || '查看评估详情'}
                            </span>
                          </span>
                          <time className="activity-time tabular">{formatDateTime(item.created_at)}</time>
                        </Link>
                      </li>
                    ))}
                  </ol>
                )}
              </SectionCard>
            </div>

            <aside className="dashboard-side">
              <SectionCard title="风险构成" description="基于全部评估记录。">
                <div className="risk-distribution">
                  {data.risk_distribution.map((slice) => (
                    <div className="risk-dist-row" key={slice.tier}>
                      <div className="risk-dist-head">
                        <span className={`risk-dot ${TONE_CLASS[slice.tone]}`} aria-hidden="true" />
                        <span>{slice.label}</span>
                        <strong className="tabular">{slice.count}</strong>
                      </div>
                      <div className="thin-track" aria-hidden="true">
                        <span
                          className={`thin-track-fill ${TONE_CLASS[slice.tone]}`}
                          style={{ width: `${Math.min(slice.percent, 100)}%` }}
                        />
                      </div>
                      <span className="risk-dist-percent tabular">{slice.percent.toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
                <div className="risk-dist-foot">
                  <span>高风险 + 极高风险需优先复核。</span>
                </div>
              </SectionCard>

              <SectionCard
                title="运行状态"
                extra={<Link to="/models">查看详情</Link>}
                description={data.model_status.mode_label}
              >
                <dl className="meta-list">
                  <div>
                    <dt>语言模型</dt>
                    <dd>{data.model_status.model}</dd>
                  </div>
                  <div>
                    <dt>规则版本</dt>
                    <dd className="tabular">{data.model_status.rule_version}</dd>
                  </div>
                  <div>
                    <dt>提示词版本</dt>
                    <dd className="tabular">{data.model_status.prompt_version}</dd>
                  </div>
                </dl>
                <p className="card-note">{data.model_status.note}</p>
                <div className="disclaimer-line">演示模型，未经校准，不替代医生决策。</div>
              </SectionCard>
            </aside>
          </div>
        </>
      ) : null}
    </div>
  )
}
