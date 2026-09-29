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
  const [checkEnabled, setCheckEnabled] = useState(false)
  const [checkInterval, setCheckInterval] = useState(15)
  const [checking, setChecking] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const adopt = (saved: Automation) => {
    setAutomation(saved)
    setEnabled(saved.enabled)
    setRunAt(saved.run_at)
    setCheckEnabled(saved.check_enabled)
    setCheckInterval(saved.check_interval_minutes)
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
      adopt(
        await sendJson<Automation>('/automation', 'PUT', {
          enabled,
          run_at: runAt,
          check_enabled: checkEnabled,
          check_interval_minutes: checkInterval,
        }),
      )
      const daily = enabled ? `Importação agendada para ${runAt}.` : 'Importação automática desligada.'
      const check = checkEnabled
        ? ` Faciais conferidas a cada ${checkInterval} min.`
        : ' Verificação periódica desligada.'
      setMessage(daily + check)
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const checkNow = async () => {
    setChecking(true)
    setMessage(null)
    setError(null)
    try {
      const checked = await sendJson<Automation>('/automation/check', 'POST')
      setAutomation((current) =>
        current
          ? { ...current, last_check_at: checked.last_check_at, last_check_message: checked.last_check_message }
          : checked,
      )
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setChecking(false)
    }
  }

  const intervalValid = Number.isInteger(checkInterval) && checkInterval >= 1 && checkInterval <= 1440
  const changed =
    automation !== null &&
    (automation.enabled !== enabled ||
      automation.run_at !== runAt ||
      automation.check_enabled !== checkEnabled ||
      automation.check_interval_minutes !== checkInterval)

  return (
    <section className="panel">
      <h2 className="panel__title">
        Importação automática
        <button
          type="button"
          className="button button--primary panel__action"
          onClick={save}
          disabled={saving || !changed || !intervalValid}
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

      <h3 className="automation__subtitle">Verificação das faciais</h3>
      <p className="panel__hint">
        Entre duas importações, pergunta a cada facial quantas pessoas e rostos ela tem. Se
        não bater com o pMoni, sincroniza só aquela facial e completa pelo Sigma quem chegou.
        É uma consulta leve: não lê o cadastro inteiro a cada vez.
      </p>

      <div className="automation">
        <label className="automation__toggle">
          <input
            type="checkbox"
            checked={checkEnabled}
            onChange={(event) => setCheckEnabled(event.target.checked)}
          />
          Conferir as faciais periodicamente
        </label>

        <label className="automation__time">
          A cada
          <input
            className="field"
            type="number"
            min={1}
            max={1440}
            step={1}
            value={Number.isNaN(checkInterval) ? '' : checkInterval}
            disabled={!checkEnabled}
            onChange={(event) => setCheckInterval(event.target.valueAsNumber)}
          />
          minutos
        </label>

        <button
          type="button"
          className="button"
          onClick={checkNow}
          disabled={checking}
        >
          {checking ? 'Conferindo…' : 'Conferir agora'}
        </button>
      </div>

      <p className="panel__hint">
        {automation?.last_check_at
          ? `Última verificação: ${whenOf(automation.last_check_at)}`
          : 'Nenhuma verificação executada até agora.'}
      </p>

      {automation?.last_check_message && (
        <p
          className={
            /Sem resposta|Falha/.test(automation.last_check_message)
              ? 'automation__log automation__log--bad'
              : 'automation__log'
          }
        >
          {automation.last_check_message}
        </p>
      )}

      {message && <p className="panel__ok">{message}</p>}
      {error && <p className="panel__error">{error}</p>}
    </section>
  )
}
