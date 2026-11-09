import type { ReactNode } from 'react'

export function PageHeader({
  title,
  description,
  extra,
}: {
  title: string
  description?: ReactNode
  extra?: ReactNode
}) {
  return (
    <header className="page-heading">
      <div className="page-heading-copy">
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {extra ? <div className="page-heading-actions">{extra}</div> : null}
    </header>
  )
}

export function SectionCard({
  title,
  description,
  extra,
  children,
  className = '',
  padded = true,
}: {
  title?: ReactNode
  description?: ReactNode
  extra?: ReactNode
  children: ReactNode
  className?: string
  padded?: boolean
}) {
  return (
    <section className={`surface-card ${padded ? '' : 'is-flush'} ${className}`.trim()}>
      {title || extra ? (
        <div className="surface-card-head">
          <div>
            {title ? <h2>{title}</h2> : null}
            {description ? <p className="surface-card-sub">{description}</p> : null}
          </div>
          {extra ? <div className="surface-card-extra">{extra}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  )
}

export function EmptyPanel({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="empty-panel">
      <div className="empty-panel-mark" aria-hidden="true" />
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {action ? <div className="empty-panel-action">{action}</div> : null}
    </div>
  )
}

export function LoadingPanel({ label = '正在加载' }: { label?: string }) {
  return (
    <div className="loading-panel" role="status">
      <span className="loading-line" aria-hidden="true" />
      <span className="loading-line short" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  )
}
