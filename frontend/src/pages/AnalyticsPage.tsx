import {
  CheckCircleOutlined,
  FileTextOutlined,
  PercentageOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { DatePicker, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { EChartsOption } from 'echarts'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'

import { analyticsApi, apiErrorMessage } from '../api/client'
import { Chart } from '../components/Chart'
import { EmptyPanel, PageHeader, SectionCard } from '../components/Layout'
import { MetricCardView } from '../components/MetricCard'
import { formatPercent } from '../lib/format'
import type { DiseaseCount } from '../types/domain'

const { RangePicker } = DatePicker

const diseaseColumns: ColumnsType<DiseaseCount> = [
  {
    title: '病种',
    dataIndex: 'disease_name',
    key: 'disease',
    render: (value: string) => <strong className="cell-strong">{value}</strong>,
  },
  {
    title: '评估量',
    dataIndex: 'count',
    key: 'count',
    width: 120,
    align: 'right',
    sorter: (a, b) => a.count - b.count,
    render: (value: number) => <span className="tabular">{value}</span>,
  },
  {
    title: '平均风险',
    dataIndex: 'average_risk',
    key: 'average_risk',
    width: 140,
    align: 'right',
    sorter: (a, b) => a.average_risk - b.average_risk,
    render: (value: number) => <span className="tabular">{formatPercent(value)}</span>,
  },
  {
    title: '确认率',
    dataIndex: 'confirmed_rate',
    key: 'confirmed_rate',
    width: 140,
    align: 'right',
    sorter: (a, b) => a.confirmed_rate - b.confirmed_rate,
    render: (value: number) => <span className="tabular">{formatPercent(value)}</span>,
  },
]

export function AnalyticsPage() {
  const [range, setRange] = useState<[Dayjs, Dayjs]>(() => [
    dayjs().subtract(29, 'day'),
    dayjs(),
  ])

  const from = range[0].format('YYYY-MM-DD')
  const to = range[1].format('YYYY-MM-DD')

  const analytics = useQuery({
    queryKey: ['analytics', from, to],
    queryFn: () => analyticsApi.overview({ from, to }),
  })

  const data = analytics.data

  const trendOption = useMemo<EChartsOption>(() => {
    const trend = data?.trend ?? []
    return {
      animationDuration: 350,
      color: ['#1656a8', '#98a2b3', '#b42318'],
      legend: {
        top: 0,
        right: 0,
        icon: 'roundRect',
        itemWidth: 10,
        itemHeight: 4,
        textStyle: { color: '#475467', fontSize: 12 },
      },
      grid: { left: 8, right: 12, top: 38, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#101828',
        borderWidth: 0,
        padding: [8, 10],
        textStyle: { color: '#ffffff', fontSize: 12 },
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: trend.map((point) => dayjs(point.date).format('MM-DD')),
        axisLine: { lineStyle: { color: '#e4e7ec' } },
        axisTick: { show: false },
        axisLabel: { color: '#667085', fontSize: 11, interval: 'auto' },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: '#667085', fontSize: 11 },
        splitLine: { lineStyle: { color: '#eef1f5' } },
      },
      series: [
        {
          name: '评估总量',
          type: 'line',
          data: trend.map((point) => point.total),
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: { width: 2 },
          itemStyle: { borderColor: '#ffffff', borderWidth: 1 },
        },
        {
          name: '已确认',
          type: 'line',
          data: trend.map((point) => point.confirmed),
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { width: 1.5 },
          itemStyle: { borderColor: '#ffffff', borderWidth: 1 },
        },
        {
          name: '高风险',
          type: 'line',
          data: trend.map((point) => point.high_risk),
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { width: 1.5 },
          itemStyle: { borderColor: '#ffffff', borderWidth: 1 },
        },
      ],
    }
  }, [data])

  const diseaseOption = useMemo<EChartsOption>(() => {
    const rows = [...(data?.by_disease ?? [])].reverse()
    return {
      animationDuration: 350,
      grid: { left: 8, right: 32, top: 8, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: '#101828',
        borderWidth: 0,
        padding: [8, 10],
        textStyle: { color: '#ffffff', fontSize: 12 },
      },
      xAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: '#667085', fontSize: 11 },
        splitLine: { lineStyle: { color: '#eef1f5' } },
      },
      yAxis: {
        type: 'category',
        data: rows.map((row) => row.disease_name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#344054', fontSize: 12 },
      },
      series: [
        {
          name: '评估量',
          type: 'bar',
          data: rows.map((row) => row.count),
          barWidth: 12,
          itemStyle: { color: '#1656a8', borderRadius: [0, 2, 2, 0] },
          label: {
            show: true,
            position: 'right',
            color: '#475467',
            fontSize: 11,
          },
        },
      ],
    }
  }, [data])

  const specialtyTotal = data?.by_specialty.reduce((sum, item) => sum + item.count, 0) ?? 0

  return (
    <div className="page">
      <PageHeader
        title="数据分析"
        description="按评估创建日期统计，最多回溯 90 天；所有指标均来自演示数据库。"
        extra={
          <RangePicker
            value={range}
            allowClear={false}
            disabledDate={(current) => current && current > dayjs().endOf('day')}
            onChange={(values) => {
              if (values?.[0] && values?.[1]) setRange([values[0], values[1]])
            }}
          />
        }
      />

      {analytics.isError ? (
        <SectionCard>
          <div className="inline-error">
            <strong>分析数据加载失败</strong>
            <p>{apiErrorMessage(analytics.error)}</p>
          </div>
        </SectionCard>
      ) : null}

      {!data && !analytics.isError ? (
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
            <MetricCardView
              label="评估总量"
              value={data.total_assessments}
              unit="例"
              hint={`${from} 至 ${to}`}
              icon={<FileTextOutlined />}
            />
            <MetricCardView
              label="医生确认率"
              value={formatPercent(data.confirmation_rate)}
              hint={`${data.confirmed_assessments} 例已确认 · ${data.pending_assessments} 例待确认`}
              icon={<CheckCircleOutlined />}
            />
            <MetricCardView
              label="高风险评估"
              value={data.high_risk_assessments}
              unit="例"
              hint="高风险与极高风险合计"
              icon={<WarningOutlined />}
              attention={data.high_risk_assessments > 0}
            />
            <MetricCardView
              label="平均风险"
              value={formatPercent(data.average_risk)}
              hint="演示模型输出，未经校准"
              icon={<PercentageOutlined />}
            />
          </div>

          <div className="analytics-grid">
            <SectionCard
              title="评估趋势"
              description="按创建日期统计，已确认数量反映当前状态。"
            >
              {data.total_assessments > 0 ? (
                <Chart option={trendOption} height={288} ariaLabel="评估量趋势折线图" />
              ) : (
                <EmptyPanel title="所选区间没有评估" description="调整日期范围后重试。" />
              )}
            </SectionCard>

            <SectionCard title="专科分布" description="按评估例数排序。">
              {data.by_specialty.length > 0 ? (
                <div className="specialty-list">
                  {data.by_specialty.map((item) => {
                    const percent = specialtyTotal > 0 ? (item.count / specialtyTotal) * 100 : 0
                    return (
                      <div className="specialty-row" key={item.specialty}>
                        <div className="specialty-head">
                          <span>{item.specialty_label}</span>
                          <strong className="tabular">{item.count}</strong>
                        </div>
                        <div className="thin-track" aria-hidden="true">
                          <span
                            className="thin-track-fill tone-primary"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                        <span className="specialty-percent tabular">{percent.toFixed(1)}%</span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <EmptyPanel title="暂无专科数据" />
              )}
            </SectionCard>
          </div>

          <div className="analytics-grid is-lower">
            <SectionCard title="病种评估量" description="按病种统计评估例数。">
              {data.by_disease.length > 0 ? (
                <Chart option={diseaseOption} height={300} ariaLabel="病种评估量条形图" />
              ) : (
                <EmptyPanel title="暂无病种数据" />
              )}
            </SectionCard>

            <SectionCard
              title="病种质量概览"
              description="平均风险与确认率用于发现未闭环报告。"
              padded={false}
            >
              <Table<DiseaseCount>
                rowKey="disease_id"
                className="data-table"
                columns={diseaseColumns}
                dataSource={data.by_disease}
                pagination={false}
                scroll={{ x: 520 }}
                locale={{ emptyText: <div className="table-empty">暂无病种数据</div> }}
              />
            </SectionCard>
          </div>

          <div className="analytics-footnote">
            数据窗口：{from} 至 {to}。确认率以当前报告状态计算，不构成诊疗质量评价。
          </div>
        </>
      ) : null}
    </div>
  )
}
