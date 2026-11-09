import {
  ArrowLeftOutlined,
  CheckOutlined,
  LeftOutlined,
  RightOutlined,
} from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  App as AntApp,
  Button,
  Checkbox,
  Form,
  InputNumber,
  Radio,
  Select,
  Steps,
  Switch,
} from 'antd'
import type { Rule } from 'antd/es/form'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { apiErrorMessage, assessmentApi, patientApi, registryApi } from '../api/client'
import { PageHeader, SectionCard } from '../components/Layout'
import {
  fieldDisplayValue,
  formatDate,
  GENDER_LABEL,
  initials,
} from '../lib/format'
import type { FieldSpec } from '../types/domain'

type WizardFieldValue = string | number | boolean

interface WizardValues {
  patient_id?: string
  disease_id?: string
  [key: string]: WizardFieldValue | undefined
}

function fieldRules(spec: FieldSpec): Rule[] {
  const rules: Rule[] = []
  if (spec.required && spec.type !== 'boolean') {
    rules.push({ required: true, message: `请填写${spec.label}` })
  }
  if (spec.type === 'number' || spec.type === 'integer') {
    rules.push({ type: 'number', message: `${spec.label}必须是数字` })
  }
  return rules
}

function DiseaseField({ spec }: { spec: FieldSpec }) {
  const label = (
    <span className="field-label">
      {spec.label}
      {spec.required ? <span className="required-mark">必填</span> : <span className="optional-mark">选填</span>}
    </span>
  )

  if (spec.type === 'boolean') {
    return (
      <Form.Item
        name={spec.key}
        label={label}
        valuePropName="checked"
        initialValue={Boolean(spec.default)}
        extra={spec.help}
      >
        <Switch checkedChildren="是" unCheckedChildren="否" />
      </Form.Item>
    )
  }

  if (spec.type === 'select') {
    return (
      <Form.Item name={spec.key} label={label} rules={fieldRules(spec)} extra={spec.help}>
        <Select
          placeholder={`请选择${spec.label}`}
          options={spec.options}
          showSearch={spec.options.length > 8}
          optionFilterProp="label"
        />
      </Form.Item>
    )
  }

  return (
    <Form.Item
      name={spec.key}
      label={label}
      rules={fieldRules(spec)}
      extra={spec.help}
    >
      <InputNumber
        className="full-width"
        placeholder={`请输入${spec.label}`}
        min={spec.minimum ?? undefined}
        max={spec.maximum ?? undefined}
        step={spec.type === 'integer' ? 1 : (spec.step ?? 0.1)}
        precision={spec.type === 'integer' ? 0 : undefined}
        suffix={spec.unit ? <span className="field-unit">{spec.unit}</span> : undefined}
      />
    </Form.Item>
  )
}

function SelectPatientHint({ patientId }: { patientId?: string }) {
  const patient = useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => patientApi.get(patientId as string),
    enabled: Boolean(patientId),
  })

  if (!patientId) return null
  if (!patient.data) {
    return <div className="selected-patient is-loading">正在加载患者信息…</div>
  }
  const data = patient.data
  return (
    <div className="selected-patient">
      <span className="selected-patient-avatar" aria-hidden="true">
        {initials(data.name)}
      </span>
      <div>
        <strong>{data.name}</strong>
        <span>
          {GENDER_LABEL[data.gender] ?? data.gender} · {data.age} 岁 · {data.mrn}
        </span>
      </div>
      <span className="selected-patient-meta">建档 {formatDate(data.created_at)}</span>
    </div>
  )
}

export function AssessmentWizardPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { message } = AntApp.useApp()
  const [searchParams] = useSearchParams()
  const initialPatientId = searchParams.get('patientId') ?? undefined
  const [form] = Form.useForm<WizardValues>()
  const [current, setCurrent] = useState(0)
  const [reviewConfirmed, setReviewConfirmed] = useState(false)

  const registry = useQuery({
    queryKey: ['registry'],
    queryFn: registryApi.get,
    staleTime: Infinity,
  })

  const patients = useQuery({
    queryKey: ['patients', 'wizard-options'],
    queryFn: () => patientApi.list({ page: 1, size: 100 }),
  })

  const watchedValues = Form.useWatch([], form) as WizardValues | undefined
  const patientId = watchedValues?.patient_id
  const diseaseId = watchedValues?.disease_id
  const disease = useMemo(
    () => registry.data?.diseases.find((item) => item.id === diseaseId),
    [registry.data, diseaseId],
  )

  const selectedPatientId = patientId ?? initialPatientId
  const selectedPatient = patients.data?.records.find((item) => item.id === selectedPatientId)

  const createAssessment = useMutation({
    mutationFn: assessmentApi.create,
    onSuccess: (assessment) => {
      message.success('评估已生成，等待医生签核')
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['patients'] })
      void queryClient.invalidateQueries({ queryKey: ['patient', assessment.patient.id] })
      navigate(`/assessments/${assessment.id}`, { replace: true })
    },
  })

  useEffect(() => {
    if (!disease || !selectedPatient) return
    const hasAge = disease.fields.some((spec) => spec.key === 'age')
    if (hasAge && form.getFieldValue('age') === undefined) {
      form.setFieldValue('age', selectedPatient.age)
    }
  }, [disease, selectedPatient, form])

  const completedFields = useMemo(() => {
    if (!disease) return { done: 0, total: 0 }
    const required = disease.fields.filter((spec) => spec.required)
    const done = required.filter((spec) => {
      const value = watchedValues?.[spec.key]
      return value !== undefined && value !== null && value !== ''
    }).length
    return { done, total: required.length }
  }, [disease, watchedValues])

  const goToStep = (step: number) => {
    setCurrent(step)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const applyDiseaseDefaults = (nextDiseaseId: string) => {
    const definition = registry.data?.diseases.find((item) => item.id === nextDiseaseId)
    if (!definition) return
    form.setFields(definition.fields.map((spec) => ({ name: spec.key, errors: [] })))
    const patch: Partial<WizardValues> = {}
    for (const spec of definition.fields) {
      const currentValue = form.getFieldValue(spec.key)
      if (
        (currentValue === undefined || currentValue === null || currentValue === '') &&
        spec.default !== undefined &&
        spec.default !== null
      ) {
        patch[spec.key] = spec.default as WizardFieldValue
      }
    }
    if (selectedPatient?.age !== undefined) {
      const hasAge = definition.fields.some((spec) => spec.key === 'age')
      if (hasAge && patch.age === undefined && form.getFieldValue('age') === undefined) {
        patch.age = selectedPatient.age
      }
    }
    form.setFieldsValue(patch)
  }

  const handleValuesChange = (changed: Partial<WizardValues>) => {
    if (changed.disease_id) {
      applyDiseaseDefaults(String(changed.disease_id))
      setReviewConfirmed(false)
    }
    if (changed.patient_id) {
      const nextPatient = patients.data?.records.find((item) => item.id === changed.patient_id)
      const currentDisease = registry.data?.diseases.find(
        (item) => item.id === form.getFieldValue('disease_id'),
      )
      if (nextPatient && currentDisease?.fields.some((spec) => spec.key === 'age')) {
        form.setFieldValue('age', nextPatient.age)
      }
      setReviewConfirmed(false)
    }
  }

  const validateStep = async (step: number): Promise<boolean> => {
    try {
      if (step === 0) {
        await form.validateFields(['patient_id', 'disease_id'])
      } else if (step === 1 && disease) {
        await form.validateFields(disease.fields.map((spec) => spec.key))
      }
      return true
    } catch {
      return false
    }
  }

  const handleNext = async () => {
    const valid = await validateStep(current)
    if (!valid) return
    if (current === 1) setReviewConfirmed(false)
    goToStep(Math.min(current + 1, 2))
  }

  const handleBack = () => {
    setReviewConfirmed(false)
    goToStep(Math.max(current - 1, 0))
  }

  const handleSubmit = () => {
    if (!disease || !patientId) {
      message.error('请先选择患者与评估病种')
      return
    }
    if (!reviewConfirmed) {
      message.warning('请先确认已核对录入指标')
      return
    }
    const values = form.getFieldsValue(true) as WizardValues
    const inputs: Record<string, unknown> = {}
    for (const spec of disease.fields) {
      if (values[spec.key] !== undefined && values[spec.key] !== null && values[spec.key] !== '') {
        inputs[spec.key] = values[spec.key]
      }
    }
    createAssessment.mutate({
      patient_id: patientId,
      disease_id: disease.id,
      inputs,
    })
  }

  const optionList = patients.data?.records.map((patient) => ({
    value: patient.id,
    label: `${patient.name} · ${patient.mrn}`,
  }))

  const backTarget = patientId ? `/patients/${patientId}` : '/patients'

  if (registry.isError) {
    return (
      <div className="page">
        <PageHeader title="新建评估" />
        <SectionCard>
          <div className="inline-error">
            <strong>规则注册表加载失败</strong>
            <p>{apiErrorMessage(registry.error)}</p>
            <Button onClick={() => void registry.refetch()}>重试</Button>
          </div>
        </SectionCard>
      </div>
    )
  }

  return (
    <div className="page assessment-wizard-page">
      <div className="back-link-row">
        <Link to={backTarget} className="back-link">
          <ArrowLeftOutlined />
          {patientId ? '返回患者详情' : '返回患者列表'}
        </Link>
      </div>

      <PageHeader
        title="新建风险评估"
        description="依次完成患者与病种选择、临床指标录入和提交前复核。提交后报告状态为待确认。"
        extra={
          registry.data ? (
            <span className="rule-version-chip">
              规则版本 <strong>{registry.data.ruleVersion}</strong>
            </span>
          ) : null
        }
      />

      <div className="wizard-progress surface-card">
        <Steps
          current={current}
          items={[
            { title: '患者与病种', description: '确定评估对象' },
            { title: '临床指标', description: '录入结构化字段' },
            { title: '核对提交', description: '医生界面确认' },
          ]}
        />
      </div>

      <div className="wizard-layout">
        <Form<WizardValues>
          form={form}
          layout="vertical"
          requiredMark={false}
          initialValues={{ patient_id: initialPatientId }}
          onValuesChange={handleValuesChange}
          className="wizard-form"
        >
          <div className="wizard-main">
            <SectionCard
              title="第一步 · 选择患者与评估病种"
              description="每位患者一次只选择一种疾病规则；如需评估多个病种，请分别提交。"
              className={current === 0 ? '' : 'wizard-step-hidden'}
            >
              <div className="form-field-block">
                <Form.Item
                  label={
                    <span className="field-label">
                      评估患者<span className="required-mark">必填</span>
                    </span>
                  }
                  name="patient_id"
                  rules={[{ required: true, message: '请选择评估患者' }]}
                  extra={
                    <span>
                      患者不在列表中？请先前往
                      <Link to="/patients" className="inline-text-link">
                        患者管理
                      </Link>
                      建档后返回。
                    </span>
                  }
                >
                  <Select
                    showSearch
                    allowClear
                    loading={patients.isLoading}
                    placeholder="按姓名或病历号查找患者"
                    options={optionList}
                    optionFilterProp="label"
                    notFoundContent={patients.isLoading ? '加载中…' : '暂无患者'}
                  />
                </Form.Item>
                <SelectPatientHint patientId={selectedPatientId} />
              </div>

              <div className="form-field-block">
                <Form.Item
                  label={
                    <span className="field-label">
                      评估病种<span className="required-mark">必填</span>
                    </span>
                  }
                  name="disease_id"
                  rules={[{ required: true, message: '请选择评估病种' }]}
                >
                  {registry.isLoading ? (
                    <div className="disease-loading">正在加载病种规则…</div>
                  ) : (
                    <Radio.Group className="disease-grid">
                      {registry.data?.diseases.map((item) => (
                        <Radio key={item.id} value={item.id} className="disease-option">
                          <span className="disease-option-content">
                            <span className="disease-option-top">
                              <span className="neutral-tag">{item.specialty_label}</span>
                              <span className="disease-field-count">
                                {item.fields.length} 项指标
                              </span>
                            </span>
                            <strong>{item.name}</strong>
                            <span className="disease-summary">{item.summary}</span>
                          </span>
                        </Radio>
                      ))}
                    </Radio.Group>
                  )}
                </Form.Item>
              </div>
            </SectionCard>

            <SectionCard
              title={disease ? `第二步 · ${disease.name}指标` : '第二步 · 录入临床指标'}
              description={
                disease
                  ? `${disease.specialty_label} · 共 ${disease.fields.length} 项字段，带“必填”标记的字段必须填写。`
                  : '请先返回上一步选择评估病种。'
              }
              className={current === 1 ? '' : 'wizard-step-hidden'}
              extra={
                disease ? (
                  <span className="completion-chip tabular">
                    {completedFields.done} / {completedFields.total} 必填项
                  </span>
                ) : null
              }
            >
              {disease ? (
                <>
                  <div className="field-source-note">
                    <strong>录入要求</strong>
                    <p>
                      请依据病历、影像或检验结果如实填写。字段约束由规则定义；系统不会推测缺失值。
                    </p>
                  </div>
                  <div className="field-grid">
                    {disease.fields.map((spec) => (
                      <DiseaseField key={spec.key} spec={spec} />
                    ))}
                  </div>
                  <div className="wizard-source-list">
                    <span>规则来源</span>
                    <p>{disease.sources.join(' · ')}</p>
                  </div>
                </>
              ) : (
                <Alert type="info" showIcon message="尚未选择病种" />
              )}
            </SectionCard>

            <SectionCard
              title="第三步 · 核对并提交"
              description="提交前请逐项核对。提交只生成待确认报告，不会自动完成医生签核。"
              className={current === 2 ? '' : 'wizard-step-hidden'}
            >
              {disease && selectedPatient ? (
                <>
                  <div className="review-summary">
                    <div className="review-block">
                      <span className="review-label">评估患者</span>
                      <strong>{selectedPatient.name}</strong>
                      <p>
                        {GENDER_LABEL[selectedPatient.gender] ?? selectedPatient.gender} ·{' '}
                        {selectedPatient.age} 岁 · {selectedPatient.mrn}
                      </p>
                    </div>
                    <div className="review-block">
                      <span className="review-label">评估病种</span>
                      <strong>{disease.name}</strong>
                      <p>
                        {disease.specialty_label} · {disease.fields.length} 项指标
                      </p>
                    </div>
                  </div>

                  <div className="review-fields">
                    {disease.fields.map((spec) => {
                      const value = form.getFieldValue(spec.key)
                      return (
                        <div className="review-field-row" key={spec.key}>
                          <span>{spec.label}</span>
                          <strong>{fieldDisplayValue(value, spec)}</strong>
                        </div>
                      )
                    })}
                  </div>

                  <Alert
                    className="review-alert"
                    type="warning"
                    showIcon
                    message="报告提交后进入待确认状态"
                    description="确定性规则将即时生成严重程度、风险概率与处置建议。须由医生逐项复核并完成签核后，报告才被视为已确认。"
                  />

                  <Checkbox
                    checked={reviewConfirmed}
                    onChange={(event) => setReviewConfirmed(event.target.checked)}
                    className="review-confirm"
                  >
                    我已核对上述患者信息与临床指标，确认无误并提交评估。
                  </Checkbox>
                </>
              ) : (
                <Alert
                  type="warning"
                  showIcon
                  message="信息不完整"
                  description="请返回前面的步骤，选择患者与病种并完成指标录入。"
                />
              )}

              {createAssessment.isError ? (
                <Alert
                  className="review-alert"
                  type="error"
                  showIcon
                  message="评估提交失败"
                  description={apiErrorMessage(createAssessment.error)}
                />
              ) : null}
            </SectionCard>

            <div className="wizard-actions">
              <div>
                {current > 0 ? (
                  <Button icon={<LeftOutlined />} onClick={handleBack} disabled={createAssessment.isPending}>
                    上一步
                  </Button>
                ) : (
                  <Link to={backTarget}>
                    <Button>取消</Button>
                  </Link>
                )}
              </div>
              <div>
                {current < 2 ? (
                  <Button
                    type="primary"
                    onClick={() => void handleNext()}
                    disabled={current === 1 && !disease}
                  >
                    下一步
                    <RightOutlined />
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    icon={<CheckOutlined />}
                    loading={createAssessment.isPending}
                    disabled={!reviewConfirmed || !disease || !patientId}
                    onClick={handleSubmit}
                  >
                    提交评估
                  </Button>
                )}
              </div>
            </div>
          </div>

          <aside className="wizard-aside">
            <div className="wizard-aside-card">
              <div className="wizard-aside-head">
                <h2>本次评估</h2>
                <span className="neutral-tag">手工录入</span>
              </div>
              <dl className="wizard-summary-list">
                <div>
                  <dt>患者</dt>
                  <dd>{selectedPatient?.name ?? '未选择'}</dd>
                </div>
                <div>
                  <dt>病种</dt>
                  <dd>{disease?.name ?? '未选择'}</dd>
                </div>
                <div>
                  <dt>专科</dt>
                  <dd>{disease?.specialty_label ?? '—'}</dd>
                </div>
                <div>
                  <dt>规则版本</dt>
                  <dd className="tabular">{registry.data?.ruleVersion ?? '—'}</dd>
                </div>
                <div>
                  <dt>必填项进度</dt>
                  <dd className="tabular">
                    {completedFields.done} / {completedFields.total || '—'}
                  </dd>
                </div>
              </dl>

              <div className="wizard-progress-track" aria-hidden="true">
                <span
                  style={{
                    width: `${
                      completedFields.total
                        ? Math.min((completedFields.done / completedFields.total) * 100, 100)
                        : 0
                    }%`,
                  }}
                />
              </div>

              <div className="wizard-aside-note">
                <strong>数据边界</strong>
                <p>
                  本页输入仅用于本地演示评估，不发送至外部模型。请勿录入真实患者身份信息。
                </p>
              </div>
              <div className="disclaimer-line">演示模型，未经校准，不替代医生决策。</div>
            </div>

            <div className="wizard-aside-card is-quiet">
              <span className="section-eyebrow">WORKFLOW</span>
              <p>
                提交后可在报告页查看分级依据、风险驱动因素与逐条引用建议，并由医生完成签核。
              </p>
            </div>
          </aside>
        </Form>
      </div>
    </div>
  )
}
