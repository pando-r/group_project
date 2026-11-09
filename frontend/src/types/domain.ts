export type Tone = 'neutral' | 'success' | 'warning' | 'danger'
export type RiskTier = 'low' | 'moderate' | 'high' | 'critical'
export type AssessmentStatus = 'PENDING' | 'CONFIRMED'
export type UserRole = 'DOCTOR' | 'ADMIN'

export interface User {
  id: string
  username: string
  display_name: string
  role: UserRole
  created_at: string
}

export interface PatientSummary {
  id: string
  mrn: string
  name: string
  gender: string
  birth_date: string
  age: number
  created_at: string
}

export interface AssessmentBrief {
  id: string
  disease_id: string
  disease_name: string
  specialty: string
  specialty_label: string
  status: AssessmentStatus
  severity_grade: string
  severity_level: number
  severity_tone: Tone
  risk_percent: number
  risk_tier: RiskTier
  risk_tone: Tone
  created_at: string
  confirmed_at: string | null
}

export interface RiskPoint {
  assessment_id: string
  disease_name: string
  created_at: string
  risk_percent: number
  severity_level: number
}

export interface PatientListItem extends PatientSummary {
  last_assessment: AssessmentBrief | null
}

export interface PatientDetail extends PatientSummary {
  assessments: AssessmentBrief[]
  risk_trend: RiskPoint[]
}

export interface FieldOption {
  value: string
  label: string
}

export interface FieldSpec {
  key: string
  label: string
  type: 'number' | 'integer' | 'select' | 'boolean'
  unit: string | null
  required: boolean
  minimum: number | null
  maximum: number | null
  step: number | null
  default: unknown
  options: FieldOption[]
  help: string | null
}

export interface DiseaseDefinition {
  id: string
  name: string
  short_name: string
  specialty: string
  specialty_label: string
  summary: string
  sources: string[]
  fields: FieldSpec[]
}

export interface Specialty {
  id: string
  label: string
}

export interface RuleRegistry {
  ruleVersion: string
  version: { version: string; changelog: string }
  specialties: Specialty[]
  diseases: DiseaseDefinition[]
  sources: string[]
}

export interface Scale {
  min: number
  max: number
  labels: string[]
}

export interface BasisItem {
  id: string
  label: string
  value: string
  source: string
}

export interface RiskCut {
  min: number
  max: number
  label: string
}

export interface RiskDriver {
  label: string
  direction: 'increase' | 'decrease'
  detail: string
}

export interface Citation {
  type: 'rule' | 'guideline'
  id: string
  label: string
}

export interface Recommendation {
  id: string
  text: string
  priority: 'routine' | 'consider' | 'urgent'
  citations: Citation[]
}

export interface RedFlag {
  code: string
  text: string
  severity: 'warning' | 'critical'
}

export interface AssessmentResult {
  severity: {
    grade: string
    level: number
    tone: Tone
    scale: Scale
    basis: BasisItem[]
    summary: string
  }
  risk: {
    label: string
    percent: number
    tier: RiskTier
    tone: Tone
    cuts: RiskCut[]
    drivers: RiskDriver[]
    summary: string
  }
  prognosis: {
    tier: string
    summary: string
    metrics: Array<{ label: string; value: string; note: string | null }>
  }
  recommendations: Recommendation[]
  red_flags: RedFlag[]
  meta: {
    disease_id: string
    disease_name: string
    specialty: string
    rule_version: string
    disclaimer: string
  }
}

export interface AssessmentRead {
  id: string
  patient: PatientSummary
  specialty: string
  specialty_label: string
  disease_id: string
  disease_name: string
  inputs: Record<string, unknown>
  result: AssessmentResult
  status: AssessmentStatus
  decision: string | null
  note: string | null
  confirmed_by: string | null
  confirmed_by_name: string | null
  confirmed_at: string | null
  model_version: string
  created_at: string
  updated_at: string
}

export interface AssessmentQueueItem {
  id: string
  patient_id: string
  patient_name: string
  mrn: string
  disease_id: string
  disease_name: string
  specialty: string
  severity_grade: string
  severity_level: number
  risk_percent: number
  risk_tier: RiskTier
  created_at: string
}

export interface MetricCard {
  key: string
  label: string
  value: number
  unit: string | null
  hint: string | null
}

export interface RiskSlice {
  tier: RiskTier
  label: string
  count: number
  percent: number
  tone: Tone
}

export interface ActivityItem {
  assessment_id: string
  patient_name: string
  action: string
  detail: string
  created_at: string
}

export interface ModelStatus {
  mode: string
  mode_label: string
  model: string
  prompt_version: string
  rule_version: string
  note: string
}

export interface DashboardResponse {
  metrics: MetricCard[]
  pending_queue: AssessmentQueueItem[]
  risk_distribution: RiskSlice[]
  recent_activity: ActivityItem[]
  model_status: ModelStatus
}

export interface TrendPoint {
  date: string
  total: number
  confirmed: number
  pending: number
  high_risk: number
}

export interface DiseaseCount {
  disease_id: string
  disease_name: string
  count: number
  average_risk: number
  confirmed_rate: number
}

export interface SpecialtyCount {
  specialty: string
  specialty_label: string
  count: number
}

export interface AnalyticsOverview {
  total_assessments: number
  confirmed_assessments: number
  pending_assessments: number
  high_risk_assessments: number
  confirmation_rate: number
  average_risk: number
  trend: TrendPoint[]
  by_disease: DiseaseCount[]
  by_specialty: SpecialtyCount[]
}

export interface ModelCard {
  id: string
  name: string
  kind: string
  status: string
  version: string
  description: string
}

export interface ModelsResponse {
  llm_mode: string
  llm_model: string
  prompt_version: string
  rule_version: string
  cards: ModelCard[]
}

export interface AuditLog {
  id: string
  assessment_id: string
  actor_id: string
  actor_name: string
  action: string
  detail: Record<string, unknown>
  created_at: string
}

export type AgentRunStatus = 'RUNNING' | 'WAITING_HUMAN' | 'DONE' | 'FAILED'
export type AgentDecision = 'APPROVE' | 'REJECT'
export type AgentStepStatus = 'STARTED' | 'OK' | 'ERROR'

export interface AgentDraftFact {
  key: string
  value: string
}

export interface AgentDraftSection {
  heading: string
  body: string
  evidence_ids: string[]
}

export interface AgentDraft {
  title: string
  summary: string
  risk_explanation: string
  key_points: string[]
  sections: AgentDraftSection[]
  recommendation_ids: string[]
  evidence_ids: string[]
  facts: AgentDraftFact[]
  disclaimer: string
}

export interface AgentVerification {
  schema_passed: boolean
  numeric_passed: boolean
  citation_passed: boolean
  rewrite_rounds: number
  errors: string[]
}

export interface AgentStep {
  id: string
  seq: number
  node: string
  tool_name: string | null
  input: Record<string, unknown> | null
  output: Record<string, unknown> | null
  status: AgentStepStatus
  latency_ms: number | null
  created_at: string
}

export interface AgentRun {
  id: string
  patient_id: string
  patient_name: string
  assessment_id: string | null
  disease_id: string
  disease_name: string
  status: AgentRunStatus
  model: string
  prompt_version: string
  tokens_in: number | null
  tokens_out: number | null
  latency_ms: number | null
  draft: AgentDraft | null
  verification: AgentVerification | null
  decision: AgentDecision | null
  rejection_reason: string | null
  error: string | null
  created_at: string
  updated_at: string
  steps: AgentStep[]
}

export interface AgentRunQueueItem {
  id: string
  assessment_id: string | null
  disease_id: string
  disease_name: string
  status: AgentRunStatus
  model: string
  created_at: string
}

export interface AgentFeedback {
  id: string
  run_id: string
  doctor_id: string
  rating: number
  comment: string | null
  created_at: string
}

export interface PageResponse<T> {
  page: number
  size: number
  total: number
  records: T[]
}

export interface ErrorEnvelope {
  code: string
  message: string
  data: unknown
  traceId: string
}
