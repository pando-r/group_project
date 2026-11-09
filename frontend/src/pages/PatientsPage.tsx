import { DownloadOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { ProTable } from '@ant-design/pro-components'
import type { ProColumns } from '@ant-design/pro-components'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  App as AntApp,
  Button,
  DatePicker,
  Form,
  Input,
  Modal,
  Select,
} from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import {
  apiErrorMessage,
  patientApi,
  registryApi,
} from '../api/client'
import { RiskBadge } from '../components/Badges'
import { PageHeader } from '../components/Layout'
import {
  downloadBlob,
  formatDate,
  formatDateTime,
  formatPercent,
  GENDER_LABEL,
  RISK_LABEL,
  riskTone,
  severityTone,
  TONE_CLASS,
} from '../lib/format'
import type { CreatePatientPayload } from '../api/client'
import type { PatientListItem } from '../types/domain'

interface PatientFormValues {
  mrn: string
  name: string
  gender: string
  birth_date: Dayjs
}

const STATUS_OPTIONS = [
  { value: 'PENDING', label: '待确认' },
  { value: 'CONFIRMED', label: '已确认' },
]

const RISK_OPTIONS = Object.entries(RISK_LABEL).map(([value, label]) => ({ value, label }))

const GENDER_OPTIONS = Object.entries(GENDER_LABEL).map(([value, label]) => ({ value, label }))

export function PatientsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { message } = AntApp.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const [createOpen, setCreateOpen] = useState(false)
  const [form] = Form.useForm<PatientFormValues>()

  const q = searchParams.get('q') ?? ''
  const specialty = searchParams.get('specialty') ?? undefined
  const status = searchParams.get('status') ?? undefined
  const risk = searchParams.get('risk') ?? undefined
  const page = Number(searchParams.get('page') ?? '1')
  const size = Number(searchParams.get('size') ?? '20')

  const patients = useQuery({
    queryKey: ['patients', { page, size, q, specialty, status, risk }],
    queryFn: () => patientApi.list({ page, size, q, specialty, status, risk }),
  })

  const registry = useQuery({
    queryKey: ['registry'],
    queryFn: registryApi.get,
    staleTime: Infinity,
  })

  const updateParams = (updates: Record<string, string | undefined>, resetPage = true) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (resetPage) next.set('page', '1')
    setSearchParams(next, { replace: true })
  }

  const resetFilters = () => {
    setSearchParams(new URLSearchParams(), { replace: true })
  }

  const exportCsv = useMutation({
    mutationFn: () => patientApi.exportCsv({ q, specialty, status, risk }),
    onSuccess: (blob) => {
      downloadBlob(blob, `medrisk-patients-${dayjs().format('YYYYMMDD-HHmm')}.csv`)
      message.success('患者列表已导出')
    },
    onError: (error) => message.error(apiErrorMessage(error, '导出失败')),
  })

  const createPatient = useMutation({
    mutationFn: (payload: CreatePatientPayload) => patientApi.create(payload),
    onSuccess: (patient) => {
      message.success('患者档案已创建')
      void queryClient.invalidateQueries({ queryKey: ['patients'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      setCreateOpen(false)
      form.resetFields()
      navigate(`/patients/${patient.id}`)
    },
  })

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      createPatient.mutate({
        mrn: values.mrn.trim().toUpperCase(),
        name: values.name.trim(),
        gender: values.gender,
        birth_date: values.birth_date.format('YYYY-MM-DD'),
      })
    } catch {
      // Ant Design renders the field-level validation messages.
    }
  }

  const closeCreate = () => {
    setCreateOpen(false)
    createPatient.reset()
    form.resetFields()
  }

  const columns: ProColumns<PatientListItem>[] = [
    {
      title: '患者',
      dataIndex: 'name',
      key: 'patient',
      width: 180,
      fixed: 'left',
      render: (_, record) => (
        <div className="cell-stack">
          <Link
            className="cell-link"
            to={`/patients/${record.id}`}
            onClick={(event) => event.stopPropagation()}
          >
            {record.name}
          </Link>
          <span className="cell-muted">{record.mrn}</span>
        </div>
      ),
    },
    {
      title: '性别 / 年龄',
      key: 'demographics',
      width: 110,
      render: (_, record) => (
        <span>
          {GENDER_LABEL[record.gender] ?? record.gender} · {record.age} 岁
        </span>
      ),
    },
    {
      title: '最近评估',
      key: 'disease',
      width: 170,
      render: (_, record) =>
        record.last_assessment ? (
          <div className="cell-stack">
            <strong className="cell-strong">{record.last_assessment.disease_name}</strong>
            <span className="cell-muted">{record.last_assessment.specialty_label}</span>
          </div>
        ) : (
          <span className="cell-muted">尚未评估</span>
        ),
    },
    {
      title: '分级',
      key: 'severity',
      width: 110,
      render: (_, record) =>
        record.last_assessment ? (
          <RiskBadge
            tone={severityTone(record.last_assessment.severity_level)}
            label={record.last_assessment.severity_grade}
          />
        ) : (
          <span className="cell-muted">—</span>
        ),
    },
    {
      title: '风险概率',
      key: 'risk',
      width: 120,
      sorter: (a, b) =>
        (a.last_assessment?.risk_percent ?? -1) - (b.last_assessment?.risk_percent ?? -1),
      render: (_, record) =>
        record.last_assessment ? (
          <span className="risk-inline">
            <strong>{formatPercent(record.last_assessment.risk_percent)}</strong>
            <small
              className={`risk-inline-label ${TONE_CLASS[riskTone(record.last_assessment.risk_tier)]}`}
            >
              {RISK_LABEL[record.last_assessment.risk_tier]}
            </small>
          </span>
        ) : (
          <span className="cell-muted">—</span>
        ),
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_, record) =>
        record.last_assessment ? (
          <span className={`status-badge ${record.last_assessment.status === 'CONFIRMED' ? 'is-confirmed' : 'is-pending'}`}>
            <span className="status-badge-dot" aria-hidden="true" />
            {record.last_assessment.status === 'CONFIRMED' ? '已确认' : '待确认'}
          </span>
        ) : (
          <span className="cell-muted">未评估</span>
        ),
    },
    {
      title: '最近评估时间',
      key: 'assessed_at',
      width: 155,
      sorter: (a, b) => dayjs(a.last_assessment?.created_at ?? 0).valueOf() - dayjs(b.last_assessment?.created_at ?? 0).valueOf(),
      render: (_, record) => (
        <span className="tabular cell-muted">
          {record.last_assessment ? formatDateTime(record.last_assessment.created_at) : '—'}
        </span>
      ),
    },
    {
      title: '建档日期',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (_, record) => <span className="tabular">{formatDate(record.created_at)}</span>,
    },
    {
      title: '',
      key: 'action',
      width: 80,
      fixed: 'right',
      align: 'right',
      render: (_, record) => (
        <Link
          className="table-action"
          to={`/patients/${record.id}`}
          onClick={(event) => event.stopPropagation()}
        >
          查看
        </Link>
      ),
    },
  ]

  return (
    <div className="page">
      <PageHeader
        title="患者管理"
        description="按最近一次评估展示风险状态；点击行进入患者详情与随访记录。"
        extra={
          <>
            <Button
              icon={<DownloadOutlined />}
              loading={exportCsv.isPending}
              onClick={() => exportCsv.mutate()}
            >
              导出 CSV
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新建患者
            </Button>
          </>
        }
      />

      <section className="surface-card patient-list-card" aria-label="患者列表">
        <div className="list-toolbar">
          <div className="list-toolbar-filters">
            <Input.Search
              key={q}
              defaultValue={q}
              allowClear
              placeholder="搜索姓名或病历号"
              className="patient-search"
              onSearch={(value) => updateParams({ q: value.trim() || undefined })}
            />
            <Select
              allowClear
              placeholder="全部专科"
              value={specialty}
              options={registry.data?.specialties.map((item) => ({
                value: item.id,
                label: item.label,
              }))}
              onChange={(value) => updateParams({ specialty: value })}
              className="filter-select"
            />
            <Select
              allowClear
              placeholder="全部状态"
              value={status}
              options={STATUS_OPTIONS}
              onChange={(value) => updateParams({ status: value })}
              className="filter-select"
            />
            <Select
              allowClear
              placeholder="全部风险"
              value={risk}
              options={RISK_OPTIONS}
              onChange={(value) => updateParams({ risk: value })}
              className="filter-select"
            />
            <Button
              type="text"
              onClick={resetFilters}
              disabled={!q && !specialty && !status && !risk}
            >
              重置
            </Button>
          </div>
          <div className="list-toolbar-meta">
            <span>
              共 <strong className="tabular">{patients.data?.total ?? 0}</strong> 位患者
            </span>
            <Button
              type="text"
              icon={<ReloadOutlined />}
              aria-label="刷新列表"
              onClick={() => void patients.refetch()}
              loading={patients.isRefetching}
            />
          </div>
        </div>

        {patients.isError ? (
          <div className="table-error">
            <Alert
              type="error"
              showIcon
              message="患者列表加载失败"
              description={apiErrorMessage(patients.error)}
            />
          </div>
        ) : null}

        <ProTable<PatientListItem>
          rowKey="id"
          className="patient-pro-table"
          columns={columns}
          dataSource={patients.data?.records ?? []}
          loading={patients.isFetching}
          search={false}
          options={false}
          toolBarRender={false}
          cardProps={{ bodyStyle: { padding: 0 } }}
          pagination={{
            current: page,
            pageSize: size,
            total: patients.data?.total ?? 0,
            showSizeChanger: true,
            pageSizeOptions: [10, 20, 50, 100],
            showTotal: (total, range) => `第 ${range[0]}–${range[1]} 条 / 共 ${total} 条`,
            onChange: (nextPage, nextSize) => {
              updateParams(
                {
                  page: String(nextPage),
                  size: String(nextSize),
                },
                nextSize !== size,
              )
            },
          }}
          scroll={{ x: 1180 }}
          locale={{ emptyText: <div className="table-empty">没有找到符合条件的患者</div> }}
          onRow={(record) => ({
            onClick: () => navigate(`/patients/${record.id}`),
            style: { cursor: 'pointer' },
          })}
        />
      </section>

      <Modal
        title="新建患者档案"
        open={createOpen}
        onCancel={closeCreate}
        onOk={() => void handleCreate()}
        okText="创建档案"
        cancelText="取消"
        confirmLoading={createPatient.isPending}
        destroyOnHidden
        width={500}
      >
        <p className="modal-intro">
          请确认处于演示环境。病历号需要唯一，创建后将立即写入数据库并保留操作记录。
        </p>
        {createPatient.isError ? (
          <Alert
            className="modal-alert"
            type="error"
            showIcon
            message={apiErrorMessage(createPatient.error)}
          />
        ) : null}
        <Form<PatientFormValues>
          form={form}
          layout="vertical"
          requiredMark={false}
          initialValues={{ gender: 'UNKNOWN' }}
        >
          <Form.Item
            label="病历号"
            name="mrn"
            rules={[
              { required: true, message: '请输入病历号' },
              { min: 3, max: 32, message: '病历号长度为 3–32 位' },
              { pattern: /^[A-Za-z0-9_-]+$/, message: '仅支持字母、数字、下划线与连字符' },
            ]}
          >
            <Input placeholder="例如 MR-2026-019" maxLength={32} />
          </Form.Item>
          <Form.Item
            label="姓名"
            name="name"
            rules={[{ required: true, message: '请输入姓名' }, { max: 100 }]}
          >
            <Input placeholder="请输入患者姓名" maxLength={100} />
          </Form.Item>
          <div className="form-two-col">
            <Form.Item
              label="性别"
              name="gender"
              rules={[{ required: true, message: '请选择性别' }]}
            >
              <Select options={GENDER_OPTIONS} />
            </Form.Item>
            <Form.Item
              label="出生日期"
              name="birth_date"
              rules={[{ required: true, message: '请选择出生日期' }]}
            >
              <DatePicker
                className="full-width"
                placeholder="选择日期"
                disabledDate={(current) => current && current > dayjs().endOf('day')}
              />
            </Form.Item>
          </div>
        </Form>
        <p className="modal-footnote">演示环境禁止录入真实患者身份信息。</p>
      </Modal>
    </div>
  )
}
