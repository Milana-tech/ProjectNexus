import { useEffect, useState } from 'react'

type DbResponse = {
  ok: boolean
  now?: string
  error?: string
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [health, setHealth] = useState<string>('loading...')
  const [db, setDb] = useState<DbResponse | null>(null)

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => r.json())
      .then((d) => setHealth(d.status ?? 'unknown'))
      .catch(() => setHealth('error'))

    fetch(`${API_URL}/db`)
      .then((r) => r.json())
      .then((d) => setDb(d))
      .catch(() => setDb({ ok: false, error: 'error' }))
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 24 }}>
      <h1>Project Nexus</h1>
      <p>API health: {health}</p>
      <h2>Database</h2>
      <pre style={{ background: '#111', color: '#eee', padding: 12, borderRadius: 8 }}>
        {JSON.stringify(db, null, 2)}
      </pre>
    </div>
  )
}
