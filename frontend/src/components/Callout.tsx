import type { ReactNode } from 'react'

type Props = {
  tone?: 'info' | 'warn' | 'fail' | 'pass'
  title?: string
  children: ReactNode
}

export function Callout({ tone = 'info', title, children }: Props) {
  return (
    <div className={`callout ${tone}`} role={tone === 'fail' ? 'alert' : 'status'}>
      {title ? <strong>{title}</strong> : null}
      <div>{children}</div>
    </div>
  )
}
