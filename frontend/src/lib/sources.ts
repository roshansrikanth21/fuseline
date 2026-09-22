export const SOURCES = ['location', 'browsing', 'app_usage', 'plaso'] as const
export type Source = (typeof SOURCES)[number]

export const SOURCE_LABEL: Record<string, string> = {
  location: 'Location',
  browsing: 'Browsing',
  app_usage: 'App usage',
  plaso: 'Plaso',
}

export function isSource(value: string): value is Source {
  return (SOURCES as readonly string[]).includes(value)
}

export function laneColor(source: string): string {
  return `var(--lane-${source === 'app_usage' ? 'app' : isSource(source) ? source : 'plaso'})`
}
