import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getJson, photoUrl, sendJson } from './api'
import type { Device, Resident, SyncReport } from './types'
import './AdminScreen.css'

type Draft = { apartment: string; block: string }

function normalize(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

function ResidentPhoto({ resident }: { resident: Resident }) {
  const [failed, setFailed] = useState(false)
  if (!resident.has_photo || failed) {
    return <div className="thumb thumb--empty" aria-hidden="true" />
  }
  return (
    <img
      className="thumb"
      src={photoUrl(resident.employee_no)}
      alt={resident.name}
      onError={() => setFailed(true)}
    />
  )
}

function ResidentRow({
  resident,
  onSaved,
}: {
  resident: Resident
  onSaved: (resident: Resident) => void
}) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startEditing = () =>
    setDraft({ apartment: resident.apartment ?? '', block: resident.block ?? '' })

  const save = async () => {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const saved = await sendJson<Resident>(
        `/residents/${encodeURIComponent(resident.employee_no)}`,
        'PATCH',
        { apartment: draft.apartment.trim() || null, block: draft.block.trim() || null },
      )
      onSaved(saved)
      setDraft(null)
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className={resident.apartment ? undefined : 'row--pending'}>
      <td>
        <ResidentPhoto resident={resident} />
      </td>
      <td className="cell--name">{resident.name}</td>
      <td className="cell--id">{resident.employee_no}</td>
      {draft ? (
        <>
          <td>
            <input
              className="field"
              value={draft.apartment}
              autoFocus
              placeholder="301"
              onChange={(event) => setDraft({ ...draft, apartment: event.target.value })}
              onKeyDown={(event) => event.key === 'Enter' && save()}
            />
          </td>
          <td>
            <input
              className="field"
              value={draft.block}
              placeholder="A"
              onChange={(event) => setDraft({ ...draft, block: event.target.value })}
              onKeyDown={(event) => event.key === 'Enter' && save()}
            />
          </td>
          <td className="cell--actions">
            <button className="button button--primary" onClick={save} disabled={saving}>
              {saving ? 'Salvando…' : 'Salvar'}
            </button>
            <button className="button" onClick={() => setDraft(null)} disabled={saving}>
              Cancelar
            </button>
            {error && <span className="row__error">{error}</span>}
          </td>
        </>
      ) : (
        <>
          <td className={resident.apartment ? undefined : 'cell--missing'}>
            {resident.apartment ?? 'não informado'}
          </td>
          <td className={resident.block ? undefined : 'cell--missing'}>
            {resident.block ?? '—'}
          </td>
          <td className="cell--actions">
            <button className="button" onClick={startEditing}>
              Editar
            </button>
          </td>
        </>
      )}
    </tr>
  )
}

function Devices({ onSynced }: { onSynced: () => void }) {
  const [devices, setDevices] = useState<Device[]>([])
  const [syncing, setSyncing] = useState<number | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getJson<Device[]>('/devices')
      .then(setDevices)
      .catch((failure: Error) => setError(failure.message))
  }, [])

  const sync = async (device: Device) => {
    setSyncing(device.id)
    setMessage(null)
    setError(null)
    try {
      const report = await sendJson<SyncReport>(`/residents/sync/${device.id}`, 'POST')
      setMessage(
        `${report.created} novos, ${report.updated} atualizados, ` +
          `${report.photos_downloaded} fotos` +
          (report.failures ? `, ${report.failures} falhas` : ''),
      )
      onSynced()
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setSyncing(null)
    }
  }

  return (
    <section className="panel">
      <h2 className="panel__title">Equipamentos</h2>
      {devices.length === 0 && !error && <p className="panel__hint">Nenhum equipamento cadastrado.</p>}
      <ul className="devices">
        {devices.map((device) => (
          <li key={device.id} className="devices__item">
            <div>
              <strong>{device.name}</strong>
              <span className="devices__address">
                {device.host}:{device.port}
                {device.model ? ` · ${device.model}` : ''}
              </span>
            </div>
            <button
              className="button button--primary"
              onClick={() => sync(device)}
              disabled={syncing !== null}
            >
              {syncing === device.id ? 'Sincronizando…' : 'Sincronizar cadastro'}
            </button>
          </li>
        ))}
      </ul>
      {message && <p className="panel__ok">{message}</p>}
      {error && <p className="panel__error">{error}</p>}
    </section>
  )
}

export default function AdminScreen() {
  const [residents, setResidents] = useState<Resident[]>([])
  const [search, setSearch] = useState('')
  const [onlyPending, setOnlyPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    getJson<Resident[]>('/residents')
      .then(setResidents)
      .catch((failure: Error) => setError(failure.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  const pending = residents.filter((resident) => !resident.apartment).length

  const visible = useMemo(() => {
    const term = normalize(search.trim())
    return residents.filter((resident) => {
      if (onlyPending && resident.apartment) return false
      if (!term) return true
      return (
        normalize(resident.name).includes(term) || resident.employee_no.includes(term)
      )
    })
  }, [residents, search, onlyPending])

  const replace = (saved: Resident) =>
    setResidents((current) =>
      current.map((resident) => (resident.id === saved.id ? saved : resident)),
    )

  return (
    <main className="admin">
      <header className="admin__header">
        <h1 className="admin__title">Administração</h1>
        <Link className="button" to="/">
          Ver tela da portaria
        </Link>
      </header>

      <Devices onSynced={load} />

      <section className="panel">
        <h2 className="panel__title">
          Moradores
          <span className="panel__count">
            {residents.length} cadastrados · {pending} sem apartamento
          </span>
        </h2>

        <div className="filters">
          <input
            className="field field--search"
            placeholder="Buscar por nome ou matrícula"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <label className="filters__toggle">
            <input
              type="checkbox"
              checked={onlyPending}
              onChange={(event) => setOnlyPending(event.target.checked)}
            />
            Somente sem apartamento
          </label>
        </div>

        {error && <p className="panel__error">{error}</p>}
        {loading ? (
          <p className="panel__hint">Carregando…</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th />
                  <th>Nome</th>
                  <th>Matrícula</th>
                  <th>Apartamento</th>
                  <th>Bloco</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((resident) => (
                  <ResidentRow key={resident.id} resident={resident} onSaved={replace} />
                ))}
              </tbody>
            </table>
            {visible.length === 0 && <p className="panel__hint">Nenhum morador encontrado.</p>}
          </div>
        )}
      </section>
    </main>
  )
}
