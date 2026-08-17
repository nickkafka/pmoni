import { useEffect, useState } from 'react'
import { getJson, sendJson } from './api'
import type { ImportStatus, SigmaAccount, SigmaImportResult, SigmaIntegration } from './types'

const STATUS_LABEL: Record<ImportStatus, string> = {
  ok: 'Concluída',
  partial: 'Concluída com pendências',
  failed: 'Falhou',
}

function whenOf(moment: string): string {
  return new Date(moment).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/**
 * The Sigma connection: the token, the account, and the button that pulls.
 *
 * The token field is never filled from the server — the backend does not return it,
 * by design. Leaving it empty and saving keeps whatever is stored, which is what the
 * operator wants when they are only correcting the account.
 */
export function SigmaPanel({ onImported }: { onImported: () => void }) {
  const [sigma, setSigma] = useState<SigmaIntegration | null>(null)
  const [token, setToken] = useState('')
  const [account, setAccount] = useState('')
  const [accounts, setAccounts] = useState<SigmaAccount[] | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [unmatched, setUnmatched] = useState<string[]>([])

  const adopt = (saved: SigmaIntegration) => {
    setSigma(saved)
    setAccount(saved.account_id === null ? '' : String(saved.account_id))
    setToken('')
  }

  useEffect(() => {
    getJson<SigmaIntegration>('/sigma')
      .then(adopt)
      .catch((failure: Error) => setError(failure.message))
  }, [])

  const clear = () => {
    setMessage(null)
    setError(null)
    setUnmatched([])
  }

  const run = async <T,>(label: string, action: () => Promise<T>): Promise<T | null> => {
    clear()
    setBusy(label)
    try {
      return await action()
    } catch (failure) {
      setError((failure as Error).message)
      return null
    } finally {
      setBusy(null)
    }
  }

  const save = () =>
    run('salvando', async () => {
      const saved = await sendJson<SigmaIntegration>('/sigma', 'PUT', {
        token: token.trim() || null,
        account_id: account.trim() ? Number(account.trim()) : null,
      })
      adopt(saved)
      setMessage('Configuração salva.')
    })

  const loadAccounts = () =>
    run('contas', async () => {
      const found = await getJson<SigmaAccount[]>('/sigma/accounts')
      setAccounts(found)
      setMessage(`${found.length} conta(s) visíveis com este token.`)
    })

  const forget = () =>
    run('esquecendo', async () => {
      if (!window.confirm('Esquecer o token guardado? A importação para de funcionar até informar outro.')) return
      const saved = await sendJson<SigmaIntegration>('/sigma/token', 'DELETE')
      adopt(saved)
      setMessage('Token removido.')
    })

  const importNow = () =>
    run('importando', async () => {
      const result = await sendJson<SigmaImportResult>('/sigma/import', 'POST')
      setMessage(result.message)
      setUnmatched(result.unmatched)
      const refreshed = await getJson<SigmaIntegration>('/sigma')
      setSigma(refreshed)
      onImported()
    })

  const readyToImport = sigma?.configured && account.trim() !== ''

  return (
    <section className="panel">
      <h2 className="panel__title">
        Sigma Cloud
        <button
          type="button"
          className="button button--primary panel__action"
          onClick={importNow}
          disabled={busy !== null || !readyToImport}
        >
          {busy === 'importando' ? 'Importando…' : 'Importar do Sigma'}
        </button>
      </h2>

      <p className="panel__hint">
        Traz apartamento, bloco, CPF e RG para os moradores já sincronizados das faciais.
        A ligação é feita pela matrícula do Sigma, que é o mesmo número que a facial informa.
      </p>

      <div className="sigma">
        <label className="sigma__field">
          <span className="sigma__label">
            Token da Segware
            {sigma?.configured && <em className="sigma__saved">um token está guardado</em>}
          </span>
          <input
            className="field"
            type="password"
            autoComplete="off"
            value={token}
            placeholder={sigma?.configured ? '•••••••• (deixe vazio para manter)' : 'cole o token aqui'}
            onChange={(event) => setToken(event.target.value)}
          />
        </label>

        <label className="sigma__field sigma__field--narrow">
          <span className="sigma__label">Conta</span>
          <input
            className="field"
            inputMode="numeric"
            value={account}
            placeholder="583775"
            onChange={(event) => setAccount(event.target.value)}
          />
        </label>

        <div className="sigma__actions">
          <button type="button" className="button" onClick={save} disabled={busy !== null}>
            {busy === 'salvando' ? 'Salvando…' : 'Salvar'}
          </button>
          <button
            type="button"
            className="button"
            onClick={loadAccounts}
            disabled={busy !== null || !sigma?.configured}
          >
            {busy === 'contas' ? 'Buscando…' : 'Listar contas'}
          </button>
          {sigma?.configured && (
            <button type="button" className="button button--danger" onClick={forget} disabled={busy !== null}>
              Esquecer token
            </button>
          )}
        </div>
      </div>

      <p className="sigma__warning">
        O token é uma chave: quem o tem lê a base inteira do cliente no Sigma. Ele é
        guardado cifrado e nunca é devolvido para esta tela — por isso o campo aparece
        vazio mesmo havendo um salvo.
      </p>

      {accounts && (
        <ul className="sigma__accounts">
          {accounts.slice(0, 40).map((conta) => (
            <li key={conta.id}>
              <button type="button" className="sigma__account" onClick={() => setAccount(String(conta.id))}>
                <strong>{conta.id}</strong> {conta.name ?? '—'}
                {conta.code && <span className="sigma__code">código {conta.code}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="panel__hint">
        {sigma?.last_import_at
          ? `Última importação: ${whenOf(sigma.last_import_at)}`
          : 'Nenhuma importação do Sigma até agora.'}
        {sigma?.last_status && ` · ${STATUS_LABEL[sigma.last_status]}`}
      </p>

      {sigma?.last_message && (
        <p className={sigma.last_status === 'ok' ? 'automation__log' : 'automation__log automation__log--bad'}>
          {sigma.last_message}
        </p>
      )}

      {unmatched.length > 0 && (
        <>
          <p className="panel__hint">
            Estas pessoas estão no Sigma mas não casaram com nenhuma facial — ou não estão
            cadastradas nos equipamentos, ou o nome diverge entre os dois sistemas:
          </p>
          <ul className="transfer__skipped">
            {unmatched.slice(0, 25).map((quem) => (
              <li key={quem}>{quem}</li>
            ))}
          </ul>
        </>
      )}

      {message && <p className="panel__ok">{message}</p>}
      {error && <p className="panel__error">{error}</p>}
    </section>
  )
}
