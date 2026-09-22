export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KiB', 'MiB', 'GiB', 'TiB']
  let value = bytes / 1024
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  return `${value >= 100 ? value.toFixed(0) : value.toFixed(1)} ${units[i]}`
}

export function formatCount(n: number): string {
  return n.toLocaleString('en-US')
}

export function shortHash(hash: string, head = 12, tail = 6): string {
  if (hash.length <= head + tail + 1) return hash
  return `${hash.slice(0, head)}…${tail > 0 ? hash.slice(-tail) : ''}`
}

/** Render a URL taken from evidence as inert text with the scheme separator defanged. */
export function defangUrl(url: string): string {
  return url.replace(/^(\w+):\/\//, '$1[://]').replace(/\./g, '[.]')
}

/** Only http(s) URLs may ever be turned into anchors; evidence can contain `javascript:` URLs. */
export function isWebUrl(url: string): boolean {
  return /^https?:\/\//i.test(url.trim())
}

export function clipJson(value: unknown, maxChars = 20_000): string {
  const text = JSON.stringify(value, null, 2) ?? ''
  return text.length > maxChars ? `${text.slice(0, maxChars)}\n… (${text.length - maxChars} more characters)` : text
}
