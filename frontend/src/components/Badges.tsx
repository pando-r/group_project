import type { ReactNode } from 'react'

import { TONE_CLASS } from '../lib/format'
import type { Tone } from '../types/domain'

export function RiskBadge({
  tone,
  label,
  dot = true,
}: {
  tone: Tone
  label: string
  dot?: boolean
}) {
  return (
    <span className={`risk-badge ${TONE_CLASS[tone]}`}>
      {dot ? <span className="risk-badge-dot" aria-hidden="true" /> : null}
      {label}
    </span>
  )
}

export function StatusBadge({ status }: { status: 'PENDING' | 'CONFIRMED' }) {
  return (
    <span className={`status-badge ${status === 'CONFIRMED' ? 'is-confirmed' : 'is-pending'}`}>
      <span className="status-badge-dot" aria-hidden="true" />
      {status === 'CONFIRMED' ? '已确认' : '待确认'}
    </span>
  )
}

export function NeutralTag({ children }: { children: ReactNode }) {
  return <span className="neutral-tag">{children}</span>
}
