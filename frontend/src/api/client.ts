import axios from 'axios'

import type {
  AgentDecision,
  AgentFeedback,
  AgentRun,
  AgentRunQueueItem,
  AnalyticsOverview,
  AssessmentRead,
  AuditLog,
  DashboardResponse,
  ModelsResponse,
  PageResponse,
  PatientDetail,
  PatientListItem,
  PatientSummary,
  RuleRegistry,
  User,
} from '../types/domain'

export const client = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  timeout: 20_000,
})

client.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? ''
      const isAuthProbe = url.includes('/auth/login') || url.includes('/auth/me')
      if (!isAuthProbe && window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

export function apiErrorMessage(error: unknown, fallback = '请求失败，请稍后重试'): string {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as { message?: string } | undefined
    if (payload?.message) return payload.message
    if (error.code === 'ECONNABORTED') return '请求超时，请检查后端服务是否运行'
    if (!error.response) return '无法连接服务，请确认后端已在 8000 端口启动'
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

export interface LoginPayload {
  username: string
  password: string
}

export interface PatientListParams {
  page?: number
  size?: number
  q?: string
  specialty?: string
  status?: string
  risk?: string
}

export interface CreatePatientPayload {
  mrn: string
  name: string
  gender: string
  birth_date: string
}

export interface CreateAssessmentPayload {
  patient_id: string
  disease_id: string
  inputs: Record<string, unknown>
}

export interface ConfirmPayload {
  decision: string
  note?: string
}

export interface AgentDecisionPayload {
  decision: AgentDecision
  note?: string
  edited_draft?: Record<string, unknown>
}

export interface AgentFeedbackPayload {
  rating: number
  comment?: string
}

export const authApi = {
  login: async (payload: LoginPayload): Promise<User> => {
    const { data } = await client.post<User>('/auth/login', payload)
    return data
  },
  logout: async (): Promise<void> => {
    await client.post('/auth/logout')
  },
  me: async (): Promise<User> => {
    const { data } = await client.get<User>('/auth/me')
    return data
  },
}

export const dashboardApi = {
  get: async (): Promise<DashboardResponse> => {
    const { data } = await client.get<DashboardResponse>('/dashboard')
    return data
  },
}

export const patientApi = {
  list: async (params: PatientListParams): Promise<PageResponse<PatientListItem>> => {
    const { data } = await client.get<PageResponse<PatientListItem>>('/patients', { params })
    return data
  },
  get: async (id: string): Promise<PatientDetail> => {
    const { data } = await client.get<PatientDetail>(`/patients/${id}`)
    return data
  },
  create: async (payload: CreatePatientPayload): Promise<PatientSummary> => {
    const { data } = await client.post<PatientSummary>('/patients', payload)
    return data
  },
  exportCsv: async (params: Omit<PatientListParams, 'page' | 'size'>): Promise<Blob> => {
    const { data } = await client.get<Blob>('/patients/export.csv', {
      params,
      responseType: 'blob',
    })
    return data
  },
}

export const assessmentApi = {
  create: async (payload: CreateAssessmentPayload): Promise<AssessmentRead> => {
    const { data } = await client.post<AssessmentRead>('/assessments', payload)
    return data
  },
  get: async (id: string): Promise<AssessmentRead> => {
    const { data } = await client.get<AssessmentRead>(`/assessments/${id}`)
    return data
  },
  confirm: async (id: string, payload: ConfirmPayload): Promise<AssessmentRead> => {
    const { data } = await client.post<AssessmentRead>(`/assessments/${id}/confirm`, payload)
    return data
  },
}

export const registryApi = {
  get: async (): Promise<RuleRegistry> => {
    const { data } = await client.get<RuleRegistry>('/registry')
    return data
  },
}

export const analyticsApi = {
  overview: async (params: { from?: string; to?: string }): Promise<AnalyticsOverview> => {
    const { data } = await client.get<AnalyticsOverview>('/analytics/overview', { params })
    return data
  },
}

export const modelsApi = {
  get: async (): Promise<ModelsResponse> => {
    const { data } = await client.get<ModelsResponse>('/models')
    return data
  },
}

export const auditApi = {
  list: async (assessmentId: string): Promise<AuditLog[]> => {
    const { data } = await client.get<AuditLog[]>('/audit', {
      params: { assessment_id: assessmentId },
    })
    return data
  },
}

export const agentApi = {
  createRun: async (payload: { assessment_id: string; focus?: string }): Promise<AgentRun> => {
    const { data } = await client.post<AgentRun>('/agent/runs', payload)
    return data
  },
  listRuns: async (params: {
    assessment_id?: string
    limit?: number
  }): Promise<AgentRunQueueItem[]> => {
    const { data } = await client.get<AgentRunQueueItem[]>('/agent/runs', { params })
    return data
  },
  getRun: async (id: string): Promise<AgentRun> => {
    const { data } = await client.get<AgentRun>(`/agent/runs/${id}`)
    return data
  },
  decide: async (id: string, payload: AgentDecisionPayload): Promise<AgentRun> => {
    const { data } = await client.post<AgentRun>(`/agent/runs/${id}/approve`, payload)
    return data
  },
  feedback: async (id: string, payload: AgentFeedbackPayload): Promise<AgentFeedback> => {
    const { data } = await client.post<AgentFeedback>(`/agent/runs/${id}/feedback`, payload)
    return data
  },
  streamUrl: (id: string): string => `/api/v1/agent/runs/${id}/stream`,
}
