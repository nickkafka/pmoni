import { useEffect, useState } from 'react'
import { getJson, sendJson } from './api'
import type { ImportAutomation as Automation, ImportStatus } from './types'

const STATUS_LABEL: Record<ImportStatus, string> = {
  ok: 'Concluída',
  partial: 'Concluída com falhas',
  failed: 'Falhou',
}

function whenOf(moment: string): string {
  return new Date(moment).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * The daily import, and how the last one went.
 *
 * The outcome is on the same screen as the schedule for a reason: a routine that
 * runs at three in the morning is invisible, and the operator has no other way to
 * learn that it has been failing for a week.
 */
export function ImportAutomationPanel() {
  const [automation, setAutomation] = useState<Automation | null>(null)
  const [enabled, setEnabled] = useState(false)
  const [runAt, setRunAt] = useState('03:00')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const adopt = (saved: Automation) => {
    setAutomation(saved)
    setEnabled(saved.enabled)
    setRunAt(saved.run_at)
  }

  useEffect(() => {
    getJson<Automation>('/automation')
      .then(adopt)
      .catch((failure: Error) => setError(failure.message))
  }, [])

  const save = async () => {
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      adopt(await sendJson<Automation>('/automation', 'PUT', { enabled, run_at: runAt }))
      setMessage(enabled ? `Importação agendada para ${runAt}.` : 'Importação automática desligada.')
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const changed =
    automation !== null && (automation.enabled !== enabled || automation.run_at !== runAt)

  return (
    <section className="panel">
      <h2 className="panel__title">
        Importação automática
        <button
          type="button"
          className="button button--primary panel__action"
          onClick={save}
          disabled={saving || !changed}
        >
          {saving ? 'Salvando…' : 'Salvar'}
        </button>
      </h2>

      <div className="automation">
        <label className="automation__toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          Importar os cadastros das faciais todos os dias
        </label>

        <label className="automation__time">
          Horário
          <input
            className="field"
            type="time"
            value={runAt}
            disabled={!enabled}
            onChange={(event) => setRunAt(event.target.value)}
          />
        </label>
      </div>

      <p className="panel__hint">
        {automation?.last_run_at
          ? `Última importação: ${whenOf(automation.last_run_at)}`
          : 'Nenhuma importação automática executada até agora.'}
        {automation?.last_status && ` · ${STATUS_LABEL[automation.last_status]}`}
      </p>

      {automation?.last_message && (
        <p
          className={
            automation.last_status === 'ok' ? 'automation__log' : 'automation__log automation__log--bad'
          }
        >
          {automation.last_message}
        </p>
      )}

      {message && <p className="panel__ok">{message}</p>}
      {error && <p className="panel__error">{error}</p>}
    </section>
  )
}
