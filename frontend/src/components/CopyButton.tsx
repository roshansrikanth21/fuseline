import { useEffect, useRef, useState } from 'react'

type Props = {
  value: string
  label?: string
  className?: string
}

async function writeClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Clipboard API needs a secure context; loopback counts, but fall back for odd embeddings.
    const area = document.createElement('textarea')
    area.value = text
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    area.remove()
    return ok
  }
}

export function CopyButton({ value, label = 'Copy', className = '' }: Props) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  return (
    <button
      type="button"
      className={`btn ghost small copy-btn ${className}`.trim()}
      onClick={async (e) => {
        e.preventDefault()
        e.stopPropagation()
        const ok = await writeClipboard(value)
        if (!ok) return
        setCopied(true)
        clearTimeout(timer.current)
        timer.current = setTimeout(() => setCopied(false), 1500)
      }}
      aria-label={copied ? 'Copied' : label}
      title={copied ? 'Copied' : label}
    >
      {copied ? 'Copied' : label}
    </button>
  )
}
