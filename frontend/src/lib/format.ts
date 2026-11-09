import dayjs from 'dayjs'

import type { AssessmentStatus, FieldSpec, RiskTier, Tone, User } from '../types/domain'

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return dayjs(value).format('YYYY-MM-DD')
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

export function formatPercent(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`
}

export const GENDER_LABEL: Record<string, string> = {
  MALE: '男',
  FEMALE: '女',
  OTHER: '其他',
  UNKNOWN: '未知',
}

export const STATUS_LABEL: Record<AssessmentStatus, string> = {
  PENDING: '待确认',
  CONFIRMED: '已确认',
}

export const ROLE_LABEL: Record<User['role'], string> = {
  DOCTOR: '医生',
  ADMIN: '管理员',
}

export const RISK_LABEL: Record<RiskTier, string> = {
  low: '低危',
  moderate: '中危',
  high: '高危',
  critical: '极高危',
}

export const TONE_CLASS: Record<Tone, string> = {
  neutral: 'tone-neutral',
  success: 'tone-success',
  warning: 'tone-warning',
  danger: 'tone-danger',
}

export function riskTone(tier: RiskTier): Tone {
  if (tier === 'critical') return 'danger'
  if (tier === 'high') return 'danger'
  if (tier === 'moderate') return 'warning'
  return 'success'
}

export function severityTone(level: number): Tone {
  if (level >= 4) return 'danger'
  if (level === 3) return 'warning'
  return 'success'
}

export function fieldDisplayValue(value: unknown, spec: FieldSpec): string {
  if (value === null || value === undefined || value === '') return '未填写'
  if (spec.type === 'boolean') return value ? '是' : '否'
  if (spec.type === 'select') {
    const option = spec.options.find((item) => item.value === String(value))
    return option?.label ?? String(value)
  }
  const display = typeof value === 'number' ? String(value) : String(value)
  return spec.unit ? `${display} ${spec.unit}` : display
}

export function initials(name: string): string {
  return name.trim().slice(0, 1) || '?'
}

export function pageTitleForPath(pathname: string): string {
  if (pathname === '/') return '临床工作台'
  if (pathname.startsWith('/patients/')) return '患者详情'
  if (pathname.startsWith('/patients')) return '患者管理'
  if (pathname === '/assessments/new') return '新建评估'
  if (pathname.startsWith('/assessments/')) return '评估报告'
  if (pathname.startsWith('/analytics')) return '数据分析'
  if (pathname.startsWith('/models')) return '模型与规则'
  if (pathname.startsWith('/settings')) return '系统设置'
  return 'MedRisk'
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
