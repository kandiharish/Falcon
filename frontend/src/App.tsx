import { useState } from 'react'
import { ApiError } from './services/apiClient'
import { SystemService, type SystemHealth } from './services/systemService'

type CheckState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'success'; health: SystemHealth }
  | { kind: 'error'; message: string }

export default function App() {
  const [check, setCheck] = useState<CheckState>({ kind: 'idle' })

  async function runCheck() {
    setCheck({ kind: 'loading' })
    try {
      const health = await SystemService.getHealth()
      setCheck({ kind: 'success', health })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Something unexpected went wrong.'
      setCheck({ kind: 'error', message })
    }
  }

  return (
    <main className="page">
      <header className="brand">
        <h1>FALCON</h1>
        <p className="brand-full">Forensic Analysis and Linked Crime Observation Network</p>
        <p className="tagline">Connecting Evidence. Revealing Relationships. Supporting Investigation.</p>
      </header>

      <section className="panel" aria-labelledby="status-title">
        <div className="panel-head">
          <h2 id="status-title">System status</h2>
          <button type="button" onClick={runCheck} disabled={check.kind === 'loading'}>
            {check.kind === 'loading' ? 'Checking…' : 'Check system'}
          </button>
        </div>

        <div aria-live="polite">
          {check.kind === 'idle' && (
            <p className="muted">Run a check to confirm the browser, API and database are connected.</p>
          )}
          {check.kind === 'error' && <p className="status status-bad">✕ {check.message}</p>}
          {check.kind === 'success' && <HealthDetails health={check.health} />}
        </div>
      </section>
    </main>
  )
}

function HealthDetails({ health }: { health: SystemHealth }) {
  const { database } = health
  return (
    <dl className="checks">
      <Check label="Browser → API" ok detail="FastAPI answered" />
      <Check
        label="API → Database"
        ok={database.connected}
        detail={database.connected ? `PostgreSQL ${database.server_version}` : 'Not reachable'}
      />
      {Object.entries(database.extensions).map(([name, version]) => (
        <Check
          key={name}
          label={`Extension: ${name}`}
          ok={version !== null}
          okText="Installed"
          detail={version ? `v${version}` : 'Missing'}
        />
      ))}
    </dl>
  )
}

interface CheckProps {
  label: string
  ok: boolean
  okText?: string
  detail: string
}

function Check({ label, ok, okText = 'Connected', detail }: CheckProps) {
  return (
    <div className="check">
      <dt>{label}</dt>
      {/* Icon + text, never color alone (accessibility) */}
      <dd className={ok ? 'status status-ok' : 'status status-bad'}>
        {ok ? `✓ ${okText}` : '✕ Problem'} · {detail}
      </dd>
    </div>
  )
}
