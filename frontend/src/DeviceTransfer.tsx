import { useState } from 'react'
import { keyOf, type DeviceTransferControls } from './useDeviceTransfer'

/** Shown behind the "i", for whoever writes the file by hand instead of exporting one. */
const SCHEMA = `{
  "devices": [
    {
      "name": "Entrada da Rua",     obrigatório
      "host": "192.168.1.10",       obrigatório — IP ou nome DDNS
      "port": 80,                   opcional, padrão 80
      "username": "admin",          obrigatório
      "password": "senha",          opcional — se faltar, o sistema pergunta
      "model": "DS-K1T342MFWX",     opcional
      "enabled": true               opcional, padrão true
    }
  ]
}`

export function DeviceTransferButtons({ transfer }: { transfer: DeviceTransferControls }) {
  return (
    <>
      <button
        type="button"
        className="button"
        onClick={transfer.exportDevices}
        disabled={transfer.busy}
      >
        Exportar
      </button>
      <button
        type="button"
        className="button"
        onClick={() => transfer.file.current?.click()}
        disabled={transfer.busy}
      >
        Importar
      </button>

      <span
        className="hint"
        tabIndex={0}
        role="note"
        aria-label="Formato do arquivo de importação"
      >
        i
        <span className="hint__bubble">
          <strong className="hint__title">Formato do arquivo</strong>
          <pre className="hint__schema">{SCHEMA}</pre>
          <span className="hint__note">
            A lista sozinha também é aceita, sem o <code>devices</code> em volta. Um
            equipamento já cadastrado no mesmo endereço e porta é atualizado, não
            duplicado. A senha pode ficar de fora: os equipamentos novos são listados
            depois da importação para você digitá-las de uma vez.
          </span>
        </span>
      </span>

      <input
        ref={transfer.file}
        type="file"
        accept="application/json,.json"
        hidden
        onChange={(event) => {
          const chosen = event.target.files?.[0]
          if (chosen) transfer.importFile(chosen)
        }}
      />
    </>
  )
}

export function DeviceTransferResult({ transfer }: { transfer: DeviceTransferControls }) {
  return (
    <>
      {transfer.message && <p className="panel__ok">{transfer.message}</p>}
      {transfer.error && <p className="panel__error">{transfer.error}</p>}
      {transfer.pending.length > 0 && <PasswordPrompt transfer={transfer} />}
    </>
  )
}

/**
 * Asks for the password of each device the file brought without one.
 *
 * They are not registered until this is answered: a device stored with no usable
 * credential is one the supervisor retries and fails to reach every cycle, and
 * nothing on screen would say why.
 */
function PasswordPrompt({ transfer }: { transfer: DeviceTransferControls }) {
  const [passwords, setPasswords] = useState<Record<string, string>>({})
  const missing = transfer.pending.filter((device) => !passwords[keyOf(device)]?.trim()).length

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-labelledby="senhas-titulo">
      <div className="modal__card">
        <h3 className="modal__title" id="senhas-titulo">
          Senhas dos equipamentos importados
        </h3>
        <p className="modal__hint">
          {transfer.pending.length === 1
            ? 'Um equipamento novo veio sem senha no arquivo. Informe-a para cadastrá-lo.'
            : `${transfer.pending.length} equipamentos novos vieram sem senha no arquivo. Informe-as para cadastrá-los.`}
        </p>

        <ul className="modal__list">
          {transfer.pending.map((device) => (
            <li className="modal__row" key={keyOf(device)}>
              <div className="modal__device">
                <strong>{device.name}</strong>
                <span className="modal__address">
                  {device.host}:{device.port} · {device.username}
                </span>
              </div>
              <input
                className="field"
                type="password"
                autoComplete="new-password"
                placeholder="Senha"
                value={passwords[keyOf(device)] ?? ''}
                onChange={(event) =>
                  setPasswords((current) => ({ ...current, [keyOf(device)]: event.target.value }))
                }
              />
            </li>
          ))}
        </ul>

        <div className="modal__actions">
          <button
            type="button"
            className="button button--primary"
            disabled={transfer.busy || missing > 0}
            onClick={() => transfer.registerPending(passwords)}
          >
            {transfer.busy ? 'Cadastrando…' : 'Cadastrar'}
          </button>
          <button
            type="button"
            className="button"
            onClick={transfer.dismissPending}
            disabled={transfer.busy}
          >
            Agora não
          </button>
          {missing > 0 && (
            <span className="modal__pending">
              {missing === 1 ? 'Falta 1 senha.' : `Faltam ${missing} senhas.`}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
