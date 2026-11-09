import {
  ArrowDownOutlined,
  ArrowLeftOutlined,
  ArrowUpOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  PrinterOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseMutationResult } from '@tanstack/react-query'
import {
  Alert,
  App as AntApp,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Timeline,
  Tooltip,
} from 'antd'
import type { FormInstance } from 'antd'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiErrorMessage, assessmentApi, auditApi } from '../api/client'
import { AgentAssistantDrawer } from '../components/AgentAssistantDrawer'
import { RiskBadge, StatusBadge } from '../components/Badges'
import { PageHeader, SectionCard } from '../components/Layout'
import { useAuthStore } from '../store/auth'
import {
  formatDateTime,
  formatPercent,
  GENDER_LABEL,
  initials,
  TONE_CLASS,
} from '../lib/format'
import type { AssessmentRead, AuditLog } from '../types/domain'

const AUDIT_ACTION_LABEL: Record<string, string> = {
  ASSESSMENT_CREATED: '创建评估',
  ASSESSMENT_CONFIRMED: '医生签核',
  AGENT_ASSESSMENT_CREATED: 'AI 草稿转评估',
  AGENT_RUN_CREATED: '发起 AI 解读',
  AGENT_RUN_APPROVED: '医生批准 AI 草稿',
  AGENT_RUN_REJECTED: '医生拒绝 AI 草稿',
}

const PRIORITY_LABEL = {
  routine: '常规',
  consider: '考虑',
  urgent: '尽快',
}

const DECISION_OPTIONS = [
  { value: '同意评估结论', label: '同意评估结论' },
  { value: '同意，建议专科会诊', label: '同意，建议专科会诊' },
  { value: '需补充资料后复评', label: '需补充资料后复评' },
]

interface ConfirmValues {
  decision: string
  note?: string
}

function auditDetail(log: AuditLog): string {
  if (log.action === 'ASSESSMENT_CONFIRMED') {
    const decision = log.detail.decision
    return typeof decision === 'string' ? decision : '已完成签核'
  }
  if (log.action === 'ASSESSMENT_CREATED') {
    const parts = [log.detail.disease_id, log.detail.severity, log.detail.risk_tier].filter(Boolean)
    return parts.length > 0 ? parts.join(' · ') : '确定性规则评估'
  }
  if (log.action.startsWith('AGENT_RUN_')) {
    const runId = typeof log.detail.run_id === 'string' ? log.detail.run_id.slice(0, 8) : ''
    const decision = typeof log.detail.decision === 'string' ? log.detail.decision : ''
    const parts = [runId ? `运行 ${runId.toUpperCase()}` : '', decision].filter(Boolean)
    return parts.join(' · ')
  }
  return ''
}

function ReportSkeleton() {
  return (
    <div className="page">
      <div className="detail-skeleton" aria-busy="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  )
}

export function AssessmentReportPage() {
  const { assessmentId } = useParams<{ assessmentId: string }>()
  const queryClient = useQueryClient()
  const { message } = AntApp.useApp()
  const user = useAuthStore((state) => state.user)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [agentOpen, setAgentOpen] = useState(false)
  const [confirmForm] = Form.useForm<ConfirmValues>()

  const assessment = useQuery({
    queryKey: ['assessment', assessmentId],
    queryFn: () => assessmentApi.get(assessmentId as string),
    enabled: Boolean(assessmentId),
  })

  const audit = useQuery({
    queryKey: ['audit', assessmentId],
    queryFn: () => auditApi.list(assessmentId as string),
    enabled: Boolean(assessmentId),
  })

  const confirm = useMutation({
    mutationFn: (values: ConfirmValues) =>
      assessmentApi.confirm(assessmentId as string, {
        decision: values.decision,
        note: values.note?.trim() || undefined,
      }),
    onSuccess: (updated) => {
      message.success('报告已签核并写入审计日志')
      queryClient.setQueryData(['assessment', assessmentId], updated)
      void queryClient.invalidateQueries({ queryKey: ['audit', assessmentId] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['patients'] })
      void queryClient.invalidateQueries({
        queryKey: ['patient', updated.patient.id],
      })
      setConfirmOpen(false)
      confirmForm.resetFields()
    },
  })

  if (assessment.isError) {
    return (
      <div className="page">
        <PageHeader
          title="评估报告"
          extra={
            <Link to="/patients">
              <Button icon={<ArrowLeftOutlined />}>返回患者列表</Button>
            </Link>
          }
        />
        <SectionCard>
          <div className="inline-error">
            <strong>无法加载评估报告</strong>
            <p>{apiErrorMessage(assessment.error)}</p>
            <Link to="/patients">
              <Button>返回列表</Button>
            </Link>
          </div>
        </SectionCard>
      </div>
    )
  }

  if (!assessment.data) return <ReportSkeleton />

  const data = assessment.data
  return (
    <ReportView
      data={data}
      audit={audit.data ?? []}
      auditLoading={audit.isLoading}
      canConfirm={data.status === 'PENDING' && user?.role === 'DOCTOR'}
      canUseAgent={user?.role === 'DOCTOR'}
      agentOpen={agentOpen}
      onOpenAgent={() => setAgentOpen(true)}
      onCloseAgent={() => setAgentOpen(false)}
      confirmOpen={confirmOpen}
      confirmForm={confirmForm}
      confirmMutation={confirm}
      onOpenConfirm={() => {
        confirmForm.setFieldsValue({ decision: '同意评估结论' })
        setConfirmOpen(true)
      }}
      onCloseConfirm={() => {
        setConfirmOpen(false)
        confirm.reset()
        confirmForm.resetFields()
      }}
      onSubmitConfirm={(values) => confirm.mutate(values)}
    />
  )
}

function ReportView({
  data,
  audit,
  auditLoading,
  canConfirm,
  canUseAgent,
  agentOpen,
  onOpenAgent,
  onCloseAgent,
  confirmOpen,
  confirmForm,
  confirmMutation,
  onOpenConfirm,
  onCloseConfirm,
  onSubmitConfirm,
}: {
  data: AssessmentRead
  audit: AuditLog[]
  auditLoading: boolean
  canConfirm: boolean
  canUseAgent: boolean
  agentOpen: boolean
  onOpenAgent: () => void
  onCloseAgent: () => void
  confirmOpen: boolean
  confirmForm: FormInstance<ConfirmValues>
  confirmMutation: UseMutationResult<AssessmentRead, Error, ConfirmValues, unknown>
  onOpenConfirm: () => void
  onCloseConfirm: () => void
  onSubmitConfirm: (values: ConfirmValues) => void
}) {
  const result = data.result
  const riskPercent = Math.max(0, Math.min(result.risk.percent, 100))
  const activeCutIndex = result.risk.cuts.findIndex(
    (cut, index) =>
      riskPercent >= cut.min && (riskPercent < cut.max || index === result.risk.cuts.length - 1),
  )

  return (
    <div className="page report-page">
      <div className="back-link-row no-print">
        <Link to={`/patients/${data.patient.id}`} className="back-link">
          <ArrowLeftOutlined />
          返回患者详情
        </Link>
      </div>

      <PageHeader
        title="风险评估报告"
        description={
          <>
            {data.disease_name} · 生成于 {formatDateTime(data.created_at)} · 报告编号{' '}
            <span className="tabular">{data.id.slice(0, 8).toUpperCase()}</span>
          </>
        }
        extra={
          <div className="no-print report-actions">
            {canUseAgent ? (
              <Button icon={<BulbOutlined />} onClick={onOpenAgent}>
                AI 解读
              </Button>
            ) : (
              <Tooltip title="仅医生角色可以使用 AI 解读">
                <Button disabled icon={<BulbOutlined />}>
                  AI 解读
                </Button>
              </Tooltip>
            )}
            <Button icon={<PrinterOutlined />} onClick={() => window.print()}>
              打印报告
            </Button>
            {data.status === 'PENDING' ? (
              canConfirm ? (
                <Button type="primary" icon={<SafetyCertificateOutlined />} onClick={onOpenConfirm}>
                  签核报告
                </Button>
              ) : (
                <Tooltip title="仅医生角色可以完成签核">
                  <Button type="primary" disabled icon={<SafetyCertificateOutlined />}>
                    签核报告
                  </Button>
                </Tooltip>
              )
            ) : (
              <Button disabled icon={<CheckCircleOutlined />}>
                已完成签核
              </Button>
            )}
          </div>
        }
      />

      <div className="report-disclaimer">
        <strong>演示模型，未经校准，不替代医生决策。</strong>
        <span>
          本报告由确定性规则根据手工录入字段生成。所有概率仅用于产品演示，不得用于真实诊疗。
        </span>
      </div>

      <section className="report-banner" aria-label="报告基本信息">
        <div className="patient-banner-primary">
          <span className="patient-avatar" aria-hidden="true">
            {initials(data.patient.name)}
          </span>
          <div className="patient-identity">
            <span className="section-eyebrow">ASSESSMENT REPORT</span>
            <h2>{data.patient.name}</h2>
            <p>
              <span>{GENDER_LABEL[data.patient.gender] ?? data.patient.gender}</span>
              <span className="dot-separator" aria-hidden="true" />
              <span>{data.patient.age} 岁</span>
              <span className="dot-separator" aria-hidden="true" />
              <span className="tabular">{data.patient.mrn}</span>
            </p>
          </div>
        </div>
        <dl className="report-banner-meta">
          <div>
            <dt>评估专科</dt>
            <dd>{data.specialty_label}</dd>
          </div>
          <div>
            <dt>规则版本</dt>
            <dd className="tabular">{data.model_version}</dd>
          </div>
          <div>
            <dt>报告状态</dt>
            <dd>
              <StatusBadge status={data.status} />
            </dd>
          </div>
        </dl>
      </section>

      <div className="conclusion-grid">
        <article className={`conclusion-card ${TONE_CLASS[result.severity.tone]}`}>
          <span className="conclusion-label">严重程度</span>
          <div className="conclusion-value-row">
            <strong>{result.severity.grade}</strong>
            <span className="conclusion-level tabular">
              {result.severity.level} / {result.severity.scale.max}
            </span>
          </div>
          <p>{result.severity.summary}</p>
        </article>
        <article className={`conclusion-card ${TONE_CLASS[result.risk.tone]}`}>
          <span className="conclusion-label">综合风险</span>
          <div className="conclusion-value-row">
            <strong>{formatPercent(result.risk.percent)}</strong>
            <RiskBadge tone={result.risk.tone} label={result.risk.label} />
          </div>
          <p>{result.risk.summary}</p>
        </article>
        <article className="conclusion-card tone-neutral">
          <span className="conclusion-label">预后分层</span>
          <div className="conclusion-value-row">
            <strong>{result.prognosis.tier}</strong>
          </div>
          <p>{result.prognosis.summary}</p>
        </article>
      </div>

      <section className="risk-scale-panel" aria-label="风险分层刻度">
        <div className="risk-scale-head">
          <div>
            <h2>风险分层刻度</h2>
            <p>当前风险概率在既定切点中的位置。</p>
          </div>
          <strong className="risk-scale-current tabular">{formatPercent(result.risk.percent)}</strong>
        </div>
        <div className="risk-meter" aria-hidden="true">
          <span
            className={`risk-meter-fill ${TONE_CLASS[result.risk.tone]}`}
            style={{ width: `${riskPercent}%` }}
          />
          <span className="risk-meter-marker" style={{ left: `${riskPercent}%` }} />
        </div>
        <div className="risk-cut-grid">
          {result.risk.cuts.map((cut, index) => (
            <div
              className={`risk-cut${index === activeCutIndex ? ' is-active' : ''}`}
              key={`${cut.min}-${cut.max}`}
            >
              <span className="tabular">
                {cut.min}–{cut.max}%
              </span>
              <strong>{cut.label}</strong>
            </div>
          ))}
        </div>
      </section>

      <div className="report-grid">
        <div className="report-main">
          {result.red_flags.length > 0 ? (
            <section className="red-flag-panel" aria-label="红旗预警">
              <div className="red-flag-head">
                <span>红旗预警</span>
                <strong>{result.red_flags.length} 项</strong>
              </div>
              <ul>
                {result.red_flags.map((flag) => (
                  <li key={flag.code} className={flag.severity === 'critical' ? 'is-critical' : ''}>
                    <span aria-hidden="true" />
                    {flag.text}
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <div className="no-flag-note">
              <CheckCircleOutlined aria-hidden="true" />
              本次规则评估未触发红旗预警；仍需结合完整临床资料判断。
            </div>
          )}

          <SectionCard title="分级依据" description="每条依据对应结构化字段与规则条目。">
            <ol className="basis-list">
              {result.severity.basis.map((item, index) => (
                <li key={item.id}>
                  <span className="basis-index tabular">{String(index + 1).padStart(2, '0')}</span>
                  <div className="basis-body">
                    <div className="basis-title">
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                    </div>
                    <p>{item.source}</p>
                  </div>
                </li>
              ))}
            </ol>
          </SectionCard>

          <SectionCard title="风险驱动因素" description="仅呈现规则中明示的方向性因素。">
            {result.risk.drivers.length > 0 ? (
              <ul className="driver-list">
                {result.risk.drivers.map((driver) => (
                  <li key={`${driver.label}-${driver.direction}`}>
                    <span
                      className={`driver-direction ${driver.direction === 'increase' ? TONE_CLASS.danger : TONE_CLASS.success}`}
                      aria-hidden="true"
                    >
                      {driver.direction === 'increase' ? (
                        <ArrowUpOutlined />
                      ) : (
                        <ArrowDownOutlined />
                      )}
                    </span>
                    <div>
                      <strong>{driver.label}</strong>
                      <p>{driver.detail}</p>
                    </div>
                    <span className="driver-tag">
                      {driver.direction === 'increase' ? '升高风险' : '降低风险'}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="card-note">当前字段未命中方向性风险因素。</p>
            )}
          </SectionCard>

          <SectionCard title="预后参考" description={result.prognosis.summary}>
            <div className="prognosis-metrics">
              {result.prognosis.metrics.map((metric) => (
                <div className="prognosis-metric" key={metric.label}>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  {metric.note ? <small>{metric.note}</small> : null}
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title="处置建议"
            description="建议按优先级复核，并逐条核对引用来源。"
          >
            <ol className="recommendation-list">
              {result.recommendations.map((recommendation, index) => (
                <li key={recommendation.id}>
                  <div className="recommendation-head">
                    <span className="recommendation-index tabular">
                      R{String(index + 1).padStart(2, '0')}
                    </span>
                    <span className="neutral-tag">{PRIORITY_LABEL[recommendation.priority]}</span>
                  </div>
                  <p>{recommendation.text}</p>
                  <div className="citation-row">
                    {recommendation.citations.map((citation) => (
                      <span className="citation" key={`${citation.type}-${citation.id}`}>
                        {citation.label}
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ol>
          </SectionCard>
        </div>

        <aside className="report-side">
          <SectionCard title="医生签核">
            {data.status === 'CONFIRMED' ? (
              <div className="signoff-confirmed">
                <div className="signoff-seal">
                  <CheckCircleOutlined aria-hidden="true" />
                  <span>已签核</span>
                </div>
                <dl className="meta-list">
                  <div>
                    <dt>签核人</dt>
                    <dd>{data.confirmed_by_name ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>签核时间</dt>
                    <dd className="tabular">{formatDateTime(data.confirmed_at)}</dd>
                  </div>
                  <div>
                    <dt>签核意见</dt>
                    <dd>{data.decision ?? '—'}</dd>
                  </div>
                </dl>
                {data.note ? <blockquote className="signoff-note">{data.note}</blockquote> : null}
              </div>
            ) : (
              <div className="signoff-pending">
                <p>
                  报告尚未生效。请逐项复核分级依据、风险驱动因素与建议引用，确认后完成医生签核。
                </p>
                {canConfirm ? (
                  <Button
                    type="primary"
                    block
                    icon={<SafetyCertificateOutlined />}
                    onClick={onOpenConfirm}
                    className="no-print"
                  >
                    签核本报告
                  </Button>
                ) : (
                  <Alert
                    type="info"
                    showIcon
                    message="当前账号无签核权限"
                    description="只有医生角色可以确认评估报告。"
                  />
                )}
                <span className="signoff-footnote">签核操作将记录操作者、时间与意见。</span>
              </div>
            )}
          </SectionCard>

          <SectionCard title="评估信息">
            <dl className="meta-list">
              <div>
                <dt>评估编号</dt>
                <dd className="tabular">{data.id.slice(0, 8).toUpperCase()}</dd>
              </div>
              <div>
                <dt>规则版本</dt>
                <dd className="tabular">{data.model_version}</dd>
              </div>
              <div>
                <dt>创建时间</dt>
                <dd className="tabular">{formatDateTime(data.created_at)}</dd>
              </div>
              <div>
                <dt>更新时间</dt>
                <dd className="tabular">{formatDateTime(data.updated_at)}</dd>
              </div>
            </dl>
            <div className="disclaimer-line">{result.meta.disclaimer}</div>
          </SectionCard>

          <SectionCard title="审计记录" description="仅显示本报告相关的操作留痕。">
            {auditLoading ? (
              <p className="card-note">正在加载审计记录…</p>
            ) : audit.length > 0 ? (
              <Timeline
                className="audit-timeline"
                items={audit.map((log) => ({
                  color: '#1656a8',
                  children: (
                    <div className="audit-item">
                      <strong>{AUDIT_ACTION_LABEL[log.action] ?? log.action}</strong>
                      <span>{log.actor_name}</span>
                      <time className="tabular">{formatDateTime(log.created_at)}</time>
                      {auditDetail(log) ? <p>{auditDetail(log)}</p> : null}
                    </div>
                  ),
                }))}
              />
            ) : (
              <p className="card-note">暂无审计记录。</p>
            )}
          </SectionCard>
        </aside>
      </div>

      <Modal
        title="签核评估报告"
        open={confirmOpen}
        onCancel={onCloseConfirm}
        onOk={() => {
          void confirmForm
            .validateFields()
            .then((values) => onSubmitConfirm(values))
            .catch(() => undefined)
        }}
        okText="确认签核"
        cancelText="返回复核"
        confirmLoading={confirmMutation.isPending}
        width={480}
        className="confirm-modal no-print"
      >
        <Alert
          className="modal-alert"
          type="warning"
          showIcon
          message="签核后报告将被锁定"
          description="请确认已完成临床复核。系统将记录你的账号、时间、签核意见与来源 IP。"
        />
        {confirmMutation.isError ? (
          <Alert
            className="modal-alert"
            type="error"
            showIcon
            message={apiErrorMessage(confirmMutation.error)}
          />
        ) : null}
        <Form<ConfirmValues>
          form={confirmForm}
          layout="vertical"
          requiredMark={false}
          initialValues={{ decision: '同意评估结论' }}
        >
          <Form.Item
            label="签核意见"
            name="decision"
            rules={[{ required: true, message: '请选择签核意见' }]}
          >
            <Select options={DECISION_OPTIONS} />
          </Form.Item>
          <Form.Item label="补充说明（选填）" name="note">
            <Input.TextArea
              rows={3}
              maxLength={2000}
              showCount
              placeholder="可记录复核要点、会诊安排或需补充的资料"
            />
          </Form.Item>
        </Form>
      </Modal>

      <AgentAssistantDrawer
        assessmentId={data.id}
        open={agentOpen}
        onClose={onCloseAgent}
        canWrite={canUseAgent}
      />
    </div>
  )
}
