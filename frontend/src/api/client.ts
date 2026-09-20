export type Case = {
  id: string
  name: string
  examiner: string
  timezone: string
  notes: string
  created_at: string
  updated_at: string
  event_count: number
  artifact_count: number
  session_count: number
}

export type Artifact = {
  id: string
  source_type: string
  original_name: string
  sha256: string
  ingested_at: string
  row_count: number
}

export type TimelineEvent = {
  id: string
  artifact_id: string
  ts_utc: string
  ts_original: string
  tz_assumed: string
  source: string
  event_type: string
  title: string
  detail: Record<string, unknown>
  lat: number | null
  lon: number | null
  package: string | null
  url: string | null
  domain: string | null
  confidence: number
}

export type Session = {
  id: string
  start_utc: string
  end_utc: string
  score: number
  summary: string
  member_event_ids: string[]
  sources: string[]
}

export type Finding = {
  id: string
  severity: string
  code: string
  message: string
  created_at: string
}

export type TimelineResponse = {
  case_id: string
  events: TimelineEvent[]
  total: number
  sources: Record<string, number>
}

export type ReportSummary = {
  case: Case
  artifacts: Artifact[]
  event_count: number
  source_counts: Record<string, number>
  session_count: number
  findings: Finding[]
  sessions: Session[]
  sample_events: TimelineEvent[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new Error('Cannot reach Fuseline API. Is the backend running on :8000?')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body?.detail) {
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Request failed (${res.status})`)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  listCases: () => request<Case[]>('/api/cases'),
  createCase: (body: { name: string; examiner: string; timezone: string; notes: string }) =>
    request<Case>('/api/cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  getCase: (id: string) => request<Case>(`/api/cases/${id}`),
  deleteCase: (id: string) => request<void>(`/api/cases/${id}`, { method: 'DELETE' }),
  listArtifacts: (id: string) => request<Artifact[]>(`/api/cases/${id}/artifacts`),
  loadDemo: (id: string) =>
    request<{
      artifacts: Artifact[]
      events_added: number
      sessions_rebuilt: number
      findings: Finding[]
    }>(`/api/cases/${id}/acquire/demo`, { method: 'POST' }),
  upload: async (id: string, file: File, sourceHint: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('source_hint', sourceHint)
    return request<{
      artifact: Artifact
      events_added: number
      sessions_rebuilt: number
      findings: Finding[]
    }>(`/api/cases/${id}/acquire`, { method: 'POST', body: form })
  },
  timeline: (id: string, params?: { source?: string; q?: string }) => {
    const qs = new URLSearchParams()
    if (params?.source) qs.set('source', params.source)
    if (params?.q) qs.set('q', params.q)
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<TimelineResponse>(`/api/cases/${id}/timeline${suffix}`)
  },
  sessions: (id: string) => request<Session[]>(`/api/cases/${id}/sessions`),
  validation: (id: string, refresh = false) =>
    request<Finding[]>(`/api/cases/${id}/validation${refresh ? '?refresh=true' : ''}`),
  report: (id: string) => request<ReportSummary>(`/api/cases/${id}/report`),
}