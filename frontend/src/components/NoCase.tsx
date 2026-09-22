import { Link } from 'react-router-dom'

export function NoCase({ title }: { title: string }) {
  return (
    <section className="panel">
      <h1>{title}</h1>
      <div className="empty">
        No active case. <Link to="/">Create or open a case</Link> first.
      </div>
    </section>
  )
}
