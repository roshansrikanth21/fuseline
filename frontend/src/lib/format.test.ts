import { describe, expect, it } from 'vitest'
import { clipJson, defangUrl, formatBytes, isWebUrl, shortHash } from './format'

describe('format', () => {
  it('formats byte sizes', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(1023)).toBe('1023 B')
    expect(formatBytes(1536)).toBe('1.5 KiB')
    expect(formatBytes(64 * 1024 * 1024)).toBe('64.0 MiB')
    expect(formatBytes(-1)).toBe('—')
  })

  it('abbreviates hashes', () => {
    const h = 'a'.repeat(64)
    expect(shortHash(h)).toBe(`${'a'.repeat(12)}…${'a'.repeat(6)}`)
    expect(shortHash('abc')).toBe('abc')
  })

  it('can drop the tail entirely without repeating the whole string', () => {
    expect(shortHash('a'.repeat(64), 8, 0)).toBe(`${'a'.repeat(8)}…`)
  })

  it('defangs URLs so they cannot be clicked by accident', () => {
    expect(defangUrl('https://evil.example.com/x')).toBe('https[://]evil[.]example[.]com/x')
  })

  it('only allows http(s) URLs to become links', () => {
    expect(isWebUrl('https://a.test')).toBe(true)
    expect(isWebUrl(' HTTP://a.test')).toBe(true)
    for (const bad of ['javascript:alert(1)', 'data:text/html,<script>', 'file:///etc/passwd', 'chrome://newtab', '//x']) {
      expect(isWebUrl(bad)).toBe(false)
    }
  })

  it('clips huge JSON blobs', () => {
    expect(clipJson({ a: 1 })).toBe('{\n  "a": 1\n}')
    const clipped = clipJson({ big: 'x'.repeat(50_000) }, 100)
    expect(clipped.length).toBeLessThan(200)
    expect(clipped).toContain('more characters')
  })
})
