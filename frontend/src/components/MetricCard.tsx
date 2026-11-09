import type { ReactNode } from 'react'

export function MetricCardView({
  label,
  value,
  unit,
  hint,
  icon,
  attention = false,
}: {
  label: string
  value: number | string
  unit?: string | null
  hint?: string | null
  icon?: ReactNode
  attention?: boolean
}) {
  return (
    <article className={`metric-card${attention ? ' has-attention' : ''}`}>
      <div className="metric-card-head">
        <span>{label}</span>
        {icon ? <span className="metric-icon">{icon}</span> : null}
      </div>
      <div className="metric-value">
        <strong>{value}</strong>
        {unit ? <span>{unit}</span> : null}
      </div>
      <p className="metric-hint">{hint ?? ' '}</p>
    </article>
  )
}
