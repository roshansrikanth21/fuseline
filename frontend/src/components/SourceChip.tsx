type Props = {
  source: string
}

export function SourceChip({ source }: Props) {
  const cls = ['badge', source.replace(/\s+/g, '_')].join(' ')
  return <span className={cls}>{source}</span>
}