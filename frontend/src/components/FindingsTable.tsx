import type { Finding } from '../api/client'

const ORDER: Record<string, number> = { fail: 0, warn: 1, info: 2, pass: 3 }

export function FindingsTable({ findings, empty }: { findings: Finding[]; empty: string }) {
  if (findings.length === 0) return <div className="empty">{empty}</div>
  const sorted = [...findings].sort((a, b) => (ORDER[a.severity] ?? 9) - (ORDER[b.severity] ?? 9))
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th scope="col">Severity</th>
            <th scope="col">Code</th>
            <th scope="col">Message</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((f) => (
            <tr key={f.id}>
              <td>
                <span className={`sev sev-${f.severity}`}>{f.severity}</span>
              </td>
              <td className="mono">{f.code}</td>
              <td>{f.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
