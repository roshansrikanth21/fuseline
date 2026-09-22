import type { Artifact, Session, TimelineEvent } from '../api/client'

let counter = 0

export function makeEvent(overrides: Partial<TimelineEvent> = {}): TimelineEvent {
  counter += 1
  const ts = overrides.ts_ms ?? Date.UTC(2024, 5, 15, 10, 0, counter)
  return {
    id: `evt-${counter}`,
    artifact_id: 'art-1',
    ts_utc: new Date(ts).toISOString(),
    ts_ms: ts,
    ts_original: String(ts),
    tz_assumed: 'UTC',
    ts_basis: 'absolute',
    source: 'browsing',
    event_type: 'visit',
    title: `Event ${counter}`,
    detail: {},
    lat: null,
    lon: null,
    package: null,
    url: null,
    domain: null,
    confidence: 1,
    ...overrides,
  }
}

export function makeArtifact(overrides: Partial<Artifact> = {}): Artifact {
  return {
    id: 'art-1',
    source_type: 'browsing',
    original_name: 'History',
    sha256: 'a'.repeat(64),
    ingested_at: '2024-06-15T10:00:00.000Z',
    row_count: 3,
    size_bytes: 40_960,
    skipped_rows: 0,
    parser: 'chromium_history',
    notes: [],
    ...overrides,
  }
}

export function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    id: 'sess-1',
    start_utc: '2024-06-15T10:00:00.000Z',
    end_utc: '2024-06-15T10:20:00.000Z',
    score: 3.5,
    summary: 'app_usage + browsing: apps: com.a',
    member_event_ids: [],
    sources: ['app_usage', 'browsing'],
    event_count: 4,
    centroid_lat: null,
    centroid_lon: null,
    radius_m: null,
    ...overrides,
  }
}
