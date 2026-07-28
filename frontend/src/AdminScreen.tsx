import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, FormEvent, MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { getJson, photoUrl, remove, sendJson } from './api'
import type { Device, Resident, SyncReport } from './types'
import './AdminScreen.css'

type Draft = { apartment: string; block: string }

function normalize(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

const ZOOM_HEIGHT = 340
const ZOOM_GAP = 12

function ResidentPhoto({ resident }: { resident: Resident }) {
  const [failed, setFailed] = useState(false)
  const [zoom, setZoom] = useState<{ top: number; left: number } | null>(null)

  if (!resident.has_photo || failed) {
    return <div className="thumb thumb--empty" aria-hidden="true" />
  }

  // Fixed positioning, computed on hover: the table scrolls horizontally, and an
  // absolutely positioned preview would be clipped by that scroll container.
  const show = (event: MouseEvent<HTMLImageElement>) => {
    const anchor = event.currentTarget.getBoundingClientRect()
    setZoom({
      top: Math.max(ZOOM_GAP, Math.min(anchor.top, window.innerHeight - ZOOM_HEIGHT - ZOOM_GAP)),
      left: anchor.right + ZOOM_GAP,
    })
  }

  return (
    <>
      <img
        className="thumb"
        src={photoUrl(resident.employee_no)}
        alt={resident.name}
        onError={() => setFailed(true)}
        onMouseEnter={show}
        onMouseLeave={() => setZoom(null)}
      />
      {zoom && (
        <img
          className="thumb-zoom"
          style={{ top: zoom.top, left: zoom.left }}
          src={photoUrl(resident.employee_no)}
          alt=""
          aria-hidden="true"
        />
      )}
    </>
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

const EMPTY_DEVICE = { name: '', host: '', port: '80', username: '', password: '', model: '' }

function formOf(device: Device | null) {
  if (device === null) return EMPTY_DEVICE
  return {
    name: device.name,
    host: device.host,
    port: String(device.port),
    username: device.username,
    password: '',
    model: device.model ?? '',
  }
}

function DeviceForm({
  device,
  onSaved,
  onCancel,
}: {
  device: Device | null
  onSaved: (device: Device) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState(() => formOf(device))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const editing = device !== null

  const update = (field: keyof typeof EMPTY_DEVICE) => (event: ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [field]: event.target.value }))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const body = {
      name: form.name.trim(),
      host: form.host.trim(),
      port: Number(form.port) || 80,
      username: form.username.trim(),
      password: form.password || null,
      model: form.model.trim() || null,
      ...(editing ? { enabled: device.enabled } : {}),
    }
    try {
      const saved = editing
        ? await sendJson<Device>(`/devices/${device.id}`, 'PATCH', body)
        : await sendJson<Device>('/devices', 'POST', { ...body, password: form.password })
      onSaved(saved)
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="device-form" onSubmit={submit}>
      <label className="device-form__field device-form__field--wide">
        Nome
        <input className="field" value={form.name} onChange={update('name')} required
          placeholder="Portaria social" />
      </label>
      <label className="device-form__field device-form__field--wide">
        Endereço
        <input className="field" value={form.host} onChange={update('host')} required
          placeholder="192.168.1.10 ou nome.ddns.net" />
      </label>
      <label className="device-form__field device-form__field--narrow">
        Porta
        <input className="field" value={form.port} onChange={update('port')} inputMode="numeric" />
      </label>
      <label className="device-form__field">
        Usuário
        <input className="field" value={form.username} onChange={update('username')} required
          placeholder="admin" />
      </label>
      <label className="device-form__field">
        Senha
        <input className="field" type="password" value={form.password} onChange={update('password')}
          required={!editing} placeholder={editing ? 'manter a atual' : undefined} />
      </label>
      <label className="device-form__field">
        Modelo
        <input className="field" value={form.model} onChange={update('model')}
          placeholder="opcional" />
      </label>
      <div className="device-form__actions">
        <button className="button button--primary" type="submit" disabled={saving}>
          {saving ? 'Salvando…' : editing ? 'Salvar alterações' : 'Adicionar equipamento'}
        </button>
        <button className="button" type="button" onClick={onCancel} disabled={saving}>
          Cancelar
        </button>
        {error && <span className="row__error">{error}</span>}
      </div>
    </form>
  )
}

function Devices({ onSynced }: { onSynced: () => void }) {
  const [devices, setDevices] = useState<Device[]>([])
  const [syncing, setSyncing] = useState<number | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Device | null | undefined>(undefined)

  useEffect(() => {
    getJson<Device[]>('/devices')
      .then(setDevices)
      .catch((failure: Error) => setError(failure.message))
  }, [])

  const saved = (device: Device) => {
    setDevices((current) =>
      current.some((item) => item.id === device.id)
        ? current.map((item) => (item.id === device.id ? device : item))
        : [...current, device],
    )
    setEditing(undefined)
  }

  const discard = async (device: Device) => {
    if (!window.confirm(`Excluir "${device.name}"? O monitoramento dele para agora.`)) return
    setError(null)
    try {
      await remove(`/devices/${device.id}`)
      setDevices((current) => current.filter((item) => item.id !== device.id))
    } catch (failure) {
      setError((failure as Error).message)
    }
  }

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
      <h2 className="panel__title">
        Equipamentos
        <button
          className="button panel__action"
          onClick={() => setEditing((current) => (current === null ? undefined : null))}
        >
          {editing === null ? 'Fechar' : 'Adicionar facial'}
        </button>
      </h2>
      {editing !== undefined && (
        <DeviceForm device={editing} onSaved={saved} onCancel={() => setEditing(undefined)} />
      )}
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
            <div className="devices__actions">
              <button
                className="button button--primary"
                onClick={() => sync(device)}
                disabled={syncing !== null}
              >
                {syncing === device.id ? 'Sincronizando…' : 'Sincronizar cadastro'}
              </button>
              <button className="button" onClick={() => setEditing(device)}>
                Editar
              </button>
              <button className="button button--danger" onClick={() => discard(device)}>
                Excluir
              </button>
            </div>
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
            placeholder="Buscar por nome ou ID"
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
                  <th>ID</th>
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
