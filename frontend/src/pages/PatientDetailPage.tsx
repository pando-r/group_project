import { ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiErrorMessage, patientApi } from '../api/client'
import { RiskBadge, StatusBadge } from '../components/Badges'
import { Chart } from '../components/Chart'
import { EmptyPanel, PageHeader, SectionCard } from '../components/Layout'
import {
  formatDate,
  formatDateTime,
  formatPercent,
  GENDER_LABEL,
  initials,
  RISK_LABEL,
  riskTone,
  severityTone,
  TONE_CLASS,
} from '../lib/format'
import type { AssessmentBrief } from '../types/domain'

const historyColumns: ColumnsType<AssessmentBrief> = [
  {
    title: '评估日期',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 145,
    render: (value: string) => <span className="tabular">{formatDateTime(value)}</span>,
  },
  {
    title: '病种',
    key: 'disease',
    render: (_, record) => (
      <div className="cell-stack">
        <strong className="cell-strong">{record.disease_name}</strong>
        <span className="cell-muted">{record.specialty_label}</span>
      </div>
    ),
  },
  {
    title: '严重程度',
    key: 'severity',
    width: 120,
    render: (_, record) => (
      <RiskBadge tone={severityTone(record.severity_level)} label={record.severity_grade} />
    ),
  },
  {
    title: '风险概率',
    key: 'risk',
    width: 130,
    render: (_, record) => (
      <span className="risk-inline">
        <strong>{formatPercent(record.risk_percent)}</strong>
        <small>{RISK_LABEL[record.risk_tier]}</small>
      </span>
    ),
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (_, record) => <StatusBadge status={record.status} />,
  },
  {
    title: '',
    key: 'action',
    width: 80,
    align: 'right',
    render: (_, record) => (
      <Link className="table-action" to={`/assessments/${record.id}`}>
        查看报告
      </Link>
    ),
  },
]

export function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const patient = useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => patientApi.get(patientId as string),
    enabled: Boolean(patientId),
  })

  const data = patient.data
  const latest = data?.assessments[0]
  const trend = data?.risk_trend ?? []

  const trendOption = useMemo<EChartsOption>(() => {
    const max = Math.max(...trend.map((point) => point.risk_percent), 10)
    const axisMax = Math.ceil((max + 8) / 10) * 10
    return {
      animationDuration: 350,
      grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#101828',
        borderWidth: 0,
        padding: [8, 10],
        textStyle: { color: '#ffffff', fontSize: 12 },
        valueFormatter: (value) => `${Number(value).toFixed(1)}%`,
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: trend.map((point) => dayjs(point.created_at).format('MM-DD')),
        axisLine: { lineStyle: { color: '#e4e7ec' } },
        axisTick: { show: false },
        axisLabel: { color: '#667085', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: axisMax,
        axisLabel: { color: '#667085', fontSize: 11, formatter: '{value}%' },
        splitLine: { lineStyle: { color: '#eef1f5' } },
      },
      series: [
        {
          name: '风险概率',
          type: 'line',
          data: trend.map((point) => point.risk_percent),
          symbol: 'circle',
          symbolSize: 6,
          showSymbol: true,
          lineStyle: { color: '#1656a8', width: 2 },
          itemStyle: { color: '#1656a8', borderColor: '#ffffff', borderWidth: 1 },
          emphasis: { focus: 'series' },
        },
      ],
    }
  }, [trend])

  if (patient.isError) {
    return (
      <div className="page">
        <PageHeader
          title="患者详情"
          extra={
            <Link to="/patients">
              <Button icon={<ArrowLeftOutlined />}>返回患者列表</Button>
            </Link>
          }
        />
        <SectionCard>
          <div className="inline-error">
            <strong>无法加载患者档案</strong>
            <p>{apiErrorMessage(patient.error)}</p>
            <Link to="/patients">
              <Button>返回列表</Button>
            </Link>
          </div>
        </SectionCard>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="page">
        <PageHeader title="患者详情" />
        <div className="detail-skeleton" aria-busy="true">
          <span />
          <span />
          <span />
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="back-link-row">
        <Link to="/patients" className="back-link">
          <ArrowLeftOutlined />
          返回患者列表
        </Link>
      </div>

      <PageHeader
        title="患者详情"
        description="查看完整评估记录与风险变化，所有历史报告保持只读。"
        extra={
          <Link to={`/assessments/new?patientId=${data.id}`}>
            <Button type="primary" icon={<PlusOutlined />}>
              新建评估
            </Button>
          </Link>
        }
      />

      <section className="patient-banner" aria-label="患者基本信息">
        <div className="patient-banner-primary">
          <span className="patient-avatar" aria-hidden="true">
            {initials(data.name)}
          </span>
          <div className="patient-identity">
            <span className="section-eyebrow">PATIENT RECORD</span>
            <h2>{data.name}</h2>
            <p>
              <span>{GENDER_LABEL[data.gender] ?? data.gender}</span>
              <span className="dot-separator" aria-hidden="true" />
              <span>{data.age} 岁</span>
              <span className="dot-separator" aria-hidden="true" />
              <span className="tabular">{data.mrn}</span>
            </p>
          </div>
        </div>
        <dl className="patient-banner-meta">
          <div>
            <dt>出生日期</dt>
            <dd className="tabular">{formatDate(data.birth_date)}</dd>
          </div>
          <div>
            <dt>建档日期</dt>
            <dd className="tabular">{formatDate(data.created_at)}</dd>
          </div>
          <div>
            <dt>评估次数</dt>
            <dd className="tabular">{data.assessments.length} 次</dd>
          </div>
        </dl>
      </section>

      {latest ? (
        <section className="patient-snapshot" aria-label="最近一次评估摘要">
          <div className="snapshot-cell">
            <span>最近评估</span>
            <strong>{latest.disease_name}</strong>
            <small>{latest.specialty_label}</small>
          </div>
          <div className="snapshot-cell">
            <span>严重程度</span>
            <RiskBadge tone={severityTone(latest.severity_level)} label={latest.severity_grade} />
            <small>分级层级 {latest.severity_level}</small>
          </div>
          <div className="snapshot-cell">
            <span>风险概率</span>
            <strong
              className={`snapshot-risk ${TONE_CLASS[riskTone(latest.risk_tier)]}`}
            >
              {formatPercent(latest.risk_percent)}
            </strong>
            <small>{RISK_LABEL[latest.risk_tier]}</small>
          </div>
          <div className="snapshot-cell">
            <span>报告状态</span>
            <StatusBadge status={latest.status} />
            <small>{formatDateTime(latest.confirmed_at ?? latest.created_at)}</small>
          </div>
        </section>
      ) : null}

      <div className="patient-detail-grid">
        <div className="patient-detail-main">
          <SectionCard
            title="风险趋势"
            description="按评估时间升序展示综合风险概率，不同病种之间不可直接比较。"
          >
            {trend.length > 0 ? (
              <Chart
                option={trendOption}
                height={248}
                ariaLabel={`${data.name} 的风险概率趋势图`}
              />
            ) : (
              <EmptyPanel
                title="暂无趋势数据"
                description="完成首次评估后，这里会展示风险变化。"
              />
            )}
          </SectionCard>

          <SectionCard
            title="评估记录"
            description={`共 ${data.assessments.length} 次评估，按时间倒序排列。`}
            padded={false}
          >
            <Table<AssessmentBrief>
              rowKey="id"
              className="data-table"
              columns={historyColumns}
              dataSource={data.assessments}
              pagination={false}
              scroll={{ x: 760 }}
              locale={{
                emptyText: (
                  <EmptyPanel
                    title="尚未建立评估"
                    description="选择病种并录入临床指标，生成可复核的风险报告。"
                  />
                ),
              }}
            />
          </SectionCard>
        </div>

        <aside className="patient-detail-side">
          <SectionCard title="档案信息">
            <dl className="meta-list">
              <div>
                <dt>病历号</dt>
                <dd className="tabular">{data.mrn}</dd>
              </div>
              <div>
                <dt>性别</dt>
                <dd>{GENDER_LABEL[data.gender] ?? data.gender}</dd>
              </div>
              <div>
                <dt>年龄</dt>
                <dd className="tabular">{data.age} 岁</dd>
              </div>
              <div>
                <dt>出生日期</dt>
                <dd className="tabular">{formatDate(data.birth_date)}</dd>
              </div>
              <div>
                <dt>建档时间</dt>
                <dd className="tabular">{formatDateTime(data.created_at)}</dd>
              </div>
            </dl>
          </SectionCard>

          <SectionCard title="随访提示">
            <p className="card-note">
              风险趋势仅反映本系统记录的历史评估，不能替代影像、检验与专科查体。
              如出现红旗症状，应立即启动临床处置流程。
            </p>
            <div className="disclaimer-line">演示模型，未经校准，不替代医生决策。</div>
          </SectionCard>
        </aside>
      </div>
    </div>
  )
}
