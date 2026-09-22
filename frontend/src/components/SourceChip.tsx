import { SOURCE_LABEL, isSource } from '../lib/sources'

export function SourceChip({ source }: { source: string }) {
  return (
    <span className={`badge ${isSource(source) ? source : 'plaso'}`} title={source}>
      {SOURCE_LABEL[source] ?? source}
    </span>
  )
}
