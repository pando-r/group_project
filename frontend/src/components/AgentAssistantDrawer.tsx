import {
  BulbOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  ExperimentOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  App as AntApp,
  Button,
  Drawer,
  Input,
  Modal,
  Rate,
  Spin,
} from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'

import { agentApi, apiErrorMessage } from '../api/client'
import type { AgentDecisionPayload } from '../api/client'
import { formatDateTime } from '../lib/format'
import type {
  AgentDecision,
  AgentDraft,
  AgentRun,
  AgentRunQueueItem,
  AgentRunStatus,
  AgentStep,
  AgentVerification,
} from '../types/domain'

const NODE_LABEL: Record<string, string> = {
  intake: '读取评估上下文',
  collect: '提取结构化字段',
  compute: '复核确定性规则',
  evidence: '获取规则证据',
  draft: '生成解读草稿',
  verify: '校验数值与引用',
  review: '等待医生复核',
  sign: '记录审批决定',
  failed: '终止运行',
}

const TOOL_LABEL: Record<string, string> = {
  get_assessment_context: '读取评估上下文',
  evaluate_risk: '复核规则结果',
  fetch_rule_evidence: '读取规则证据',
}

const FACT_LABEL: Record<string, string> = {
  severity_grade: '严重程度',
  severity_level: '严重等级',
  risk_percent: '风险概率',
  risk_tier: '风险分层',
  prognosis_tier: '预后分层',
}

const RUN_STATUS_LABEL: Record<AgentRunStatus, string> = {
  RUNNING: '解析中',
  WAITING_HUMAN: '待医生复核',
  DONE: '已完成',
  FAILED: '运行失败',
}

const RUN_STATUS_CLASS: Record<AgentRunStatus, string> = {
  RUNNING: 'is-running',
  WAITING_HUMAN: 'is-waiting',
  DONE: 'is-done',
  FAILED: 'is-failed',
}

interface TimelineStep {
  seq: number
  node: string
  tool: string | null
  status: string
  latency_ms: number | null
}

function toTimeline(step: AgentStep): TimelineStep {
  return {
    seq: step.seq,
    node: step.node,
    tool: step.tool_name,
    status: step.status,
    latency_ms: step.latency_ms,
  }
}

function stepLabel(step: TimelineStep): string {
  if (step.tool) return TOOL_LABEL[step.tool] ?? step.tool
  return NODE_LABEL[step.node] ?? step.node
}

function verificationRows(verification: AgentVerification | null) {
  return [
    { key: 'schema', label: '结构校验', passed: verification?.schema_passed ?? false },
    { key: 'numeric', label: '数值一致', passed: verification?.numeric_passed ?? false },
    { key: 'citation', label: '引用可追溯', passed: verification?.citation_passed ?? false },
  ]
}

function RunStatusPill({ status }: { status: AgentRunStatus }) {
  return (
    <span className={`agent-status-pill ${RUN_STATUS_CLASS[status]}`}>
      <span className="agent-status-dot" aria-hidden="true" />
      {RUN_STATUS_LABEL[status]}
    </span>
  )
}

export function AgentAssistantDrawer({
  assessmentId,
  open,
  onClose,
  canWrite,
}: {
  assessmentId: string
  open: boolean
  onClose: () => void
  canWrite: boolean
}) {
  const { message } = AntApp.useApp()
  const queryClient = useQueryClient()
  const [history, setHistory] = useState<AgentRunQueueItem[]>([])
  const [run, setRun] = useState<AgentRun | null>(null)
  const [steps, setSteps] = useState<TimelineStep[]>([])
  const [streamError, setStreamError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)
  const [decision, setDecision] = useState<AgentDecision | null>(null)
  const [note, setNote] = useState('')
  const [editing, setEditing] = useState(false)
  const [editSummary, setEditSummary] = useState('')
  const [editRisk, setEditRisk] = useState('')
  const [editPoints, setEditPoints] = useState('')
  const [rating, setRating] = useState(0)
  const [rated, setRated] = useState(false)
  const sourceRef = useRef<EventSource | null>(null)

  const applyRun = useCallback((next: AgentRun) => {
    setRun(next)
    setSteps(next.steps.filter((step) => step.status !== 'STARTED').map(toTimeline))
    setStreamError(null)
    setPolling(false)
  }, [])

  const refreshRun = useCallback(
    async (id: string) => {
      try {
        applyRun(await agentApi.getRun(id))
      } catch {
        // The live stream state remains visible; the next explicit refresh can recover.
      }
    },
    [applyRun],
  )

  const refreshHistory = useCallback(() => {
    void agentApi
      .listRuns({ assessment_id: assessmentId, limit: 10 })
      .then(setHistory)
      .catch(() => undefined)
  }, [assessmentId])

  const closeStream = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
  }, [])

  useEffect(() => {
    if (!open) {
      closeStream()
      setRun(null)
      setSteps([])
      setStreamError(null)
      setPolling(false)
      setDecision(null)
      setNote('')
      setEditing(false)
      setRating(0)
      setRated(false)
      return
    }
    let cancelled = false
    void agentApi
      .listRuns({ assessment_id: assessmentId, limit: 10 })
      .then((items) => {
        if (cancelled) return
        setHistory(items)
        const active = items.find(
          (item) => item.status === 'RUNNING' || item.status === 'WAITING_HUMAN',
        )
        if (!active) return
        void agentApi
          .getRun(active.id)
          .then((next) => {
            if (!cancelled) applyRun(next)
          })
          .catch(() => undefined)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [open, assessmentId, applyRun, closeStream])

  const streamRunId = run?.status === 'RUNNING' ? run.id : null

  useEffect(() => {
    if (!open || !streamRunId) return
    closeStream()
    const source = new EventSource(agentApi.streamUrl(streamRunId), { withCredentials: true })
    sourceRef.current = source
    const seen = new Set<number>()

    const pushStep = (payload: TimelineStep) => {
      if (typeof payload?.seq !== 'number' || seen.has(payload.seq)) return
      seen.add(payload.seq)
      setSteps((previous) =>
        [...previous.filter((step) => step.seq !== payload.seq), payload].sort(
          (left, right) => left.seq - right.seq,
        ),
      )
    }

    const onNode = (event: Event) => {
      try {
        pushStep(JSON.parse((event as MessageEvent<string>).data) as TimelineStep)
      } catch {
        // Ignore malformed events; the run snapshot remains authoritative.
      }
    }

    const onDraft = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as {
          draft?: AgentDraft
          verification?: AgentVerification
        }
        setRun((previous) =>
          previous
            ? {
                ...previous,
                status: 'WAITING_HUMAN',
                draft: payload.draft ?? previous.draft,
                verification: payload.verification ?? previous.verification,
              }
            : previous,
        )
      } catch {
        // Ignore malformed events.
      }
    }

    const onWaiting = () => {
      closeStream()
      void refreshRun(streamRunId)
      refreshHistory()
    }

    const onDone = () => {
      closeStream()
      void refreshRun(streamRunId)
      refreshHistory()
    }

    const onServerError = (event: Event) => {
      if (event instanceof MessageEvent) {
        let text = 'AI 运行失败'
        try {
          const payload = JSON.parse(event.data) as { message?: string }
          text = payload.message ?? text
        } catch {
          // Keep the fallback message.
        }
        setStreamError(text)
        closeStream()
        void refreshRun(streamRunId)
        return
      }
      setPolling(true)
    }

    source.addEventListener('node', onNode)
    source.addEventListener('tool', onNode)
    source.addEventListener('draft', onDraft)
    source.addEventListener('waiting', onWaiting)
    source.addEventListener('done', onDone)
    source.addEventListener('error', onServerError)

    return () => {
      source.removeEventListener('node', onNode)
      source.removeEventListener('tool', onNode)
      source.removeEventListener('draft', onDraft)
      source.removeEventListener('waiting', onWaiting)
      source.removeEventListener('done', onDone)
      source.removeEventListener('error', onServerError)
      source.close()
      if (sourceRef.current === source) sourceRef.current = null
    }
  }, [open, streamRunId, closeStream, refreshRun, refreshHistory])

  const pollingId = run?.status === 'RUNNING' && polling ? run.id : null

  useEffect(() => {
    if (!open || !pollingId) return
    const timer = window.setInterval(() => {
      void agentApi
        .getRun(pollingId)
        .then((next) => {
          applyRun(next)
        })
        .catch(() => undefined)
    }, 1500)
    return () => window.clearInterval(timer)
  }, [open, pollingId, applyRun])

  const startMutation = useMutation({
    mutationFn: () => agentApi.createRun({ assessment_id: assessmentId }),
    onSuccess: (created) => {
      setSteps([])
      setStreamError(null)
      setRun(created)
      refreshHistory()
      void queryClient.invalidateQueries({ queryKey: ['audit', assessmentId] })
    },
    onError: (error) => {
      message.error(apiErrorMessage(error))
    },
  })

  const decideMutation = useMutation({
    mutationFn: (payload: AgentDecisionPayload) => {
      if (!run) throw new Error('缺少 AI 运行记录')
      return agentApi.decide(run.id, payload)
    },
    onSuccess: (next) => {
      applyRun(next)
      setDecision(null)
      setNote('')
      setEditing(false)
      message.success(
        next.decision === 'APPROVE'
          ? '已批准 AI 草稿，报告签核仍需单独完成'
          : '已拒绝该 AI 草稿',
      )
      refreshHistory()
      void queryClient.invalidateQueries({ queryKey: ['audit', assessmentId] })
    },
  })

  const feedbackMutation = useMutation({
    mutationFn: (value: number) => {
      if (!run) throw new Error('缺少 AI 运行记录')
      return agentApi.feedback(run.id, { rating: value })
    },
    onSuccess: () => {
      setRated(true)
      message.success('评价已记录，用于演示阶段的回归观察')
    },
    onError: (error) => message.error(apiErrorMessage(error)),
  })

  const draft = run?.draft ?? null
  const verification = run?.verification ?? null

  const buildEditedDraft = (): Record<string, unknown> | undefined => {
    if (!draft || !editing) return undefined
    const summary = editSummary.trim()
    const riskExplanation = editRisk.trim()
    const keyPoints = editPoints
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
    if (!summary || !riskExplanation) return undefined
    const unchanged =
      summary === draft.summary &&
      riskExplanation === draft.risk_explanation &&
      keyPoints.join('\n') === draft.key_points.join('\n')
    if (unchanged) return undefined
    return {
      ...draft,
      summary,
      risk_explanation: riskExplanation,
      key_points: keyPoints,
    }
  }

  const openDecision = (value: AgentDecision) => {
    if (value === 'APPROVE' && editing) {
      const edited = buildEditedDraft()
      if (!edited) {
        message.warning('摘要与风险解读不能为空，且需要与原文有差异')
        return
      }
    }
    setNote('')
    setDecision(value)
  }

  const submitDecision = () => {
    if (!decision) return
    const edited = decision === 'APPROVE' ? buildEditedDraft() : undefined
    if (decision === 'APPROVE' && editing && !edited) {
      message.warning('请先补充或修正草稿内容')
      return
    }
    decideMutation.mutate({
      decision,
      note: note.trim() || undefined,
      edited_draft: edited,
    })
  }

  const beginEdit = () => {
    if (!draft) return
    setEditSummary(draft.summary)
    setEditRisk(draft.risk_explanation)
    setEditPoints(draft.key_points.join('\n'))
    setEditing(true)
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width="min(580px, 100vw)"
      className="agent-drawer"
      title={
        <div className="agent-drawer-title">
          <span className="section-eyebrow">AGENT ASSISTANT</span>
          <strong>AI 临床解读</strong>
        </div>
      }
      footer={
        <div className="agent-drawer-footnote">
          AI 只生成解读草稿，不直接写库；批准草稿与报告签核是两次独立的医生操作。
        </div>
      }
    >
      <div className="agent-drawer-body">
        <div className="agent-model-strip">
          <span>
            模型 <strong>{run?.model ?? 'mock-clinical-v1'}</strong>
          </span>
          <span>
            Prompt <strong>{run?.prompt_version ?? '—'}</strong>
          </span>
          {run?.latency_ms ? (
            <span>
              耗时 <strong className="tabular">{run.latency_ms} ms</strong>
            </span>
          ) : null}
          {run?.tokens_in || run?.tokens_out ? (
            <span>
              Tokens{' '}
              <strong className="tabular">
                {run?.tokens_in ?? 0} / {run?.tokens_out ?? 0}
              </strong>
            </span>
          ) : null}
        </div>

        <Alert
          type="info"
          showIcon
          message="演示模型，未经校准"
          description="AI 仅生成可解释草稿，所有数值与引用由服务端规则校验；不替代医生判断，也不会自动修改或签核报告。"
        />

        {streamError ? (
          <Alert
            className="agent-inline-alert"
            type="error"
            showIcon
            message="AI 解读未完成"
            description={streamError}
          />
        ) : null}

        {!run ? (
          <section className="agent-intro">
            <h3>让 Agent 先读一遍结构化评估</h3>
            <p>
              Agent 会依次读取评估上下文、复核确定性规则、获取规则证据，再生成一份带引用编号的解读草稿。
              草稿必须由医生逐项复核后才能批准。
            </p>
            <ul>
              <li>只解释现有评估，不新增诊断，不修改规则结果。</li>
              <li>数值、概率与引用编号由校验器逐项比对，不一致时自动重写。</li>
              <li>外发内容已脱敏，病历文本按不可信数据处理。</li>
            </ul>
            {canWrite ? (
              <Button
                type="primary"
                icon={<BulbOutlined />}
                loading={startMutation.isPending}
                onClick={() => startMutation.mutate()}
              >
                生成 AI 解读草稿
              </Button>
            ) : (
              <Alert
                type="warning"
                showIcon
                message="当前账号无发起权限"
                description="只有医生角色可以发起、批准或拒绝 AI 解读。"
              />
            )}
          </section>
        ) : null}

        {run ? (
          <section className="agent-run-panel">
            <div className="agent-run-head">
              <RunStatusPill status={run.status} />
              <span className="agent-run-id tabular">
                运行 {run.id.slice(0, 8).toUpperCase()}
              </span>
              {run.status === 'FAILED' && canWrite ? (
                <Button
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={() => {
                    setRun(null)
                    setSteps([])
                    startMutation.mutate()
                  }}
                >
                  重新运行
                </Button>
              ) : null}
            </div>

            <ol className="agent-timeline" aria-label="Agent 执行步骤">
              {steps.map((step) => (
                <li
                  key={step.seq}
                  className={`agent-timeline-item${step.tool ? ' is-tool' : ''}${
                    step.status === 'ERROR' ? ' is-error' : ''
                  }`}
                >
                  <span className="agent-timeline-dot" aria-hidden="true" />
                  <div className="agent-timeline-body">
                    <span>{stepLabel(step)}</span>
                    {step.tool ? <em>工具</em> : null}
                  </div>
                  <span className="agent-timeline-meta tabular">
                    {step.latency_ms != null ? `${step.latency_ms} ms` : ''}
                  </span>
                </li>
              ))}
              {run.status === 'RUNNING' ? (
                <li className="agent-timeline-item is-running">
                  <Spin size="small" />
                  <div className="agent-timeline-body">
                    <span>Agent 正在执行…</span>
                  </div>
                </li>
              ) : null}
            </ol>

            {run.status === 'FAILED' ? (
              <Alert
                type="error"
                showIcon
                message="运行失败"
                description={run.error ?? '未通过校验或运行超时，请重新发起。'}
              />
            ) : null}

            {draft && (run.status === 'WAITING_HUMAN' || run.status === 'DONE') ? (
              <article className="agent-draft">
                <header className="agent-draft-head">
                  <span className="section-eyebrow">AI DRAFT · 待医生复核</span>
                  <h3>{draft.title}</h3>
                </header>

                <div className="agent-verify-row">
                  {verificationRows(verification).map((item) => (
                    <span
                      key={item.key}
                      className={`agent-verify-item${item.passed ? ' is-passed' : ' is-failed'}`}
                    >
                      {item.passed ? <CheckCircleFilled /> : <CloseCircleFilled />}
                      {item.label}
                    </span>
                  ))}
                  {verification && verification.rewrite_rounds > 0 ? (
                    <span className="agent-verify-rewrites tabular">
                      自动重写 {verification.rewrite_rounds} 轮
                    </span>
                  ) : null}
                </div>

                {verification && verification.errors.length > 0 ? (
                  <Alert
                    className="agent-inline-alert"
                    type="warning"
                    showIcon
                    message="最近一次校验未通过"
                    description={verification.errors.slice(0, 3).join('；')}
                  />
                ) : null}

                {editing ? (
                  <div className="agent-edit-form">
                    <label>
                      摘要
                      <Input.TextArea
                        rows={3}
                        maxLength={1200}
                        value={editSummary}
                        onChange={(event) => setEditSummary(event.target.value)}
                      />
                    </label>
                    <label>
                      风险解读
                      <Input.TextArea
                        rows={3}
                        maxLength={1200}
                        value={editRisk}
                        onChange={(event) => setEditRisk(event.target.value)}
                      />
                    </label>
                    <label>
                      关键点（每行一条）
                      <Input.TextArea
                        rows={4}
                        value={editPoints}
                        onChange={(event) => setEditPoints(event.target.value)}
                      />
                    </label>
                    <p className="agent-edit-note">
                      数值与引用编号不可编辑；保存时会再次通过服务端校验。
                    </p>
                  </div>
                ) : (
                  <>
                    <p className="agent-draft-summary">{draft.summary}</p>
                    <div className="agent-draft-callout">
                      <span>风险解读</span>
                      <p>{draft.risk_explanation}</p>
                    </div>
                    <ul className="agent-key-points">
                      {draft.key_points.map((point) => (
                        <li key={point}>{point}</li>
                      ))}
                    </ul>
                    {draft.sections.map((section) => (
                      <div className="agent-draft-section" key={section.heading}>
                        <h4>{section.heading}</h4>
                        <p>{section.body}</p>
                        {section.evidence_ids.length > 0 ? (
                          <div className="agent-evidence-row">
                            {section.evidence_ids.map((id) => (
                              <span className="agent-evidence" key={id}>
                                {id}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </>
                )}

                <dl className="agent-facts">
                  {draft.facts.map((fact) => (
                    <div key={fact.key}>
                      <dt>{FACT_LABEL[fact.key] ?? fact.key}</dt>
                      <dd className="tabular">{fact.value}</dd>
                    </div>
                  ))}
                </dl>

                <div className="agent-draft-disclaimer">{draft.disclaimer}</div>

                {run.status === 'WAITING_HUMAN' && canWrite ? (
                  <div className="agent-decision">
                    <div className="agent-decision-head">
                      <strong>医生复核</strong>
                      <Button
                        size="small"
                        type="link"
                        onClick={() => {
                          if (editing) {
                            setEditing(false)
                          } else {
                            beginEdit()
                          }
                        }}
                      >
                        {editing ? '取消修改' : '修改草稿'}
                      </Button>
                    </div>
                    <p>批准仅代表认可该 AI 草稿，不会自动完成报告签核。</p>
                    <div className="agent-decision-actions">
                      <Button
                        type="primary"
                        icon={<ExperimentOutlined />}
                        onClick={() => openDecision('APPROVE')}
                      >
                        批准草稿
                      </Button>
                      <Button danger onClick={() => openDecision('REJECT')}>
                        拒绝草稿
                      </Button>
                    </div>
                  </div>
                ) : null}

                {run.status === 'WAITING_HUMAN' && !canWrite ? (
                  <Alert
                    type="info"
                    showIcon
                    message="等待医生复核"
                    description="当前账号可以查看草稿，但不能批准或拒绝。"
                  />
                ) : null}

                {run.status === 'DONE' ? (
                  <div
                    className={`agent-outcome${run.decision === 'APPROVE' ? ' is-approved' : ' is-rejected'}`}
                  >
                    <strong>
                      {run.decision === 'APPROVE' ? '医生已批准该 AI 草稿' : '医生已拒绝该 AI 草稿'}
                    </strong>
                    <p>
                      {run.decision === 'APPROVE'
                        ? '报告签核仍需在报告页面单独完成，AI 不会自动签核。'
                        : run.rejection_reason || '本次草稿未采纳，可调整评估后重新发起。'}
                    </p>
                    {canWrite ? (
                      <div className="agent-feedback">
                        <span>这次解读是否有帮助？</span>
                        <Rate
                          disabled={rated || feedbackMutation.isPending}
                          value={rating}
                          onChange={(value) => {
                            setRating(value)
                            if (value > 0) feedbackMutation.mutate(value)
                          }}
                        />
                        {rated ? <em>已记录</em> : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </article>
            ) : null}
          </section>
        ) : null}

        {history.length > 0 ? (
          <section className="agent-history">
            <div className="agent-history-head">
              <strong>本评估的 AI 记录</strong>
              <span className="tabular">{history.length} 条</span>
            </div>
            <ul>
              {history.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => {
                      if (run?.id === item.id) return
                      void agentApi
                        .getRun(item.id)
                        .then(applyRun)
                        .catch((error: unknown) => message.error(apiErrorMessage(error)))
                    }}
                  >
                    <span className={`agent-history-dot ${RUN_STATUS_CLASS[item.status]}`} />
                    <span className="agent-history-state">{RUN_STATUS_LABEL[item.status]}</span>
                    <span className="agent-history-time tabular">
                      {formatDateTime(item.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>

      <Modal
        open={decision !== null}
        title={decision === 'APPROVE' ? '确认批准 AI 草稿' : '确认拒绝 AI 草稿'}
        okText={decision === 'APPROVE' ? '确认批准' : '确认拒绝'}
        cancelText="返回复核"
        okButtonProps={{ danger: decision === 'REJECT' }}
        confirmLoading={decideMutation.isPending}
        onCancel={() => setDecision(null)}
        onOk={submitDecision}
        width={480}
        className="agent-decision-modal"
      >
        <Alert
          type="warning"
          showIcon
          message="操作将写入审计日志"
          description="批准或拒绝只作用于该 AI 运行，不会修改评估结论，也不会自动签核报告。"
        />
        {editing && decision === 'APPROVE' ? (
          <p className="agent-modal-note">提交时将附带你编辑后的草稿，并由服务端重新校验。</p>
        ) : null}
        {decideMutation.isError ? (
          <Alert
            className="agent-inline-alert"
            type="error"
            showIcon
            message={apiErrorMessage(decideMutation.error)}
          />
        ) : null}
        <label className="agent-decision-note">
          审批意见（选填）
          <Input.TextArea
            rows={3}
            maxLength={2000}
            value={note}
            placeholder="记录复核要点或拒绝原因"
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
      </Modal>
    </Drawer>
  )
}
