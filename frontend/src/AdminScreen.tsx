import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, Dispatch, FormEvent, MouseEvent, SetStateAction } from 'react'
import { Link } from 'react-router-dom'
import { getJson, photoUrl, remove, sendJson } from './api'
import { ThemeToggle } from './ThemeToggle'
import { useAuth } from './authContext'
import type { Device, Resident, SyncReport } from './types'
import './AdminScreen.css'

type Draft = { apartment: string; block: string }

function normalize(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

const ZOOM_HEIGHT = 340
const ZOOM_GAP = 12

/**
 * A person, as seen across the devices that enrolled them.
 *
 * Identifiers are issued per device, so two devices may give the same number to
 * different people. Grouping by identifier *and* name keeps them apart while still
 * showing someone enrolled on several devices as a single line.
 */
type Person = {
  key: string
  employee_no: string
  name: string
  apartment: string | null
  block: string | null
  enrollments: Resident[]
}

function groupByPerson(residents: Resident[]): Person[] {
  const people = new Map<string, Person>()
  for (const resident of residents) {
    // Par sem ambiguidade: nome e identificador podem conter qualquer caractere.
    const key = JSON.stringify([resident.employee_no, resident.name])
    const person = people.get(key)
    if (person) {
      person.enrollments.push(resident)
      person.apartment ??= resident.apartment
      person.block ??= resident.block
    } else {
      people.set(key, {
        key,
        employee_no: resident.employee_no,
        name: resident.name,
        apartment: resident.apartment,
        block: resident.block,
        enrollments: [resident],
      })
    }
  }
  return [...people.values()]
}

function ResidentPhoto({ person }: { person: Person }) {
  const [failed, setFailed] = useState(false)
  const [zoom, setZoom] = useState<{ top: number; left: number } | null>(null)
  const withPhoto = person.enrollments.find((enrollment) => enrollment.has_photo)

  if (!withPhoto || failed) {
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
        src={photoUrl(withPhoto.id)}
        alt={person.name}
        onError={() => setFailed(true)}
        onMouseEnter={show}
        onMouseLeave={() => setZoom(null)}
      />
      {zoom && (
        <img
          className="thumb-zoom"
          style={{ top: zoom.top, left: zoom.left }}
          src={photoUrl(withPhoto.id)}
          alt=""
          aria-hidden="true"
        />
      )}
    </>
  )
}

function ResidentRow({
  person,
  deviceNames,
  onSaved,
}: {
  person: Person
  deviceNames: Map<number, string>
  onSaved: (residents: Resident[]) => void
}) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startEditing = () =>
    setDraft({ apartment: person.apartment ?? '', block: person.block ?? '' })

  const save = async () => {
    if (!draft) return
    setSaving(true)
    setError(null)
    const location = {
      apartment: draft.apartment.trim() || null,
      block: draft.block.trim() || null,
    }
    try {
      // The location belongs to the person, so it is written to every enrollment
      // that names them.
      const saved = await Promise.all(
        person.enrollments.map((enrollment) =>
          sendJson<Resident>(`/residents/${enrollment.id}`, 'PATCH', location),
        ),
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
    <tr className={person.apartment ? undefined : 'row--pending'}>
      <td>
        <ResidentPhoto person={person} />
      </td>
      <td className="cell--name">{person.name}</td>
      <td className="cell--id">{person.employee_no}</td>
      <td className="cell--devices">
        {person.enrollments
          .map((enrollment) => deviceNames.get(enrollment.device_id) ?? `#${enrollment.device_id}`)
          .join(', ')}
      </td>
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
            <button type="button" className="button button--primary" onClick={save} disabled={saving}>
              {saving ? 'Salvando…' : 'Salvar'}
            </button>
            <button type="button" className="button" onClick={() => setDraft(null)} disabled={saving}>
              Cancelar
            </button>
            {error && <span className="row__error">{error}</span>}
          </td>
        </>
      ) : (
        <>
          <td className={person.apartment ? undefined : 'cell--missing'}>
            {person.apartment ?? 'não informado'}
          </td>
          <td className={person.block ? undefined : 'cell--missing'}>
            {person.block ?? '—'}
          </td>
          <td className="cell--actions">
            <button type="button" className="button" onClick={startEditing}>
              Editar
            </button>
          </td>
        </>
      )}
    </tr>
  )
}

const EMPTY_DEVICE = { name: '', host: '', port: '80', username: '', password: '', model: '' }

/**
 * What the form is doing. A device with `editing` false is being copied: the
 * fields start filled but a new equipment is registered on save.
 */
type FormTarget = { device: Device | null; editing: boolean }

function formOf({ device, editing }: FormTarget) {
  if (device === null) return EMPTY_DEVICE
  return {
    // A copy that kept the name would be indistinguishable in the list.
    name: editing ? device.name : `${device.name} (cópia)`,
    host: device.host,
    port: String(device.port),
    username: device.username,
    password: '',
    model: device.model ?? '',
  }
}

function DeviceForm({
  target,
  onSaved,
  onCancel,
}: {
  target: FormTarget
  onSaved: (device: Device) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState(() => formOf(target))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { device, editing } = target
  const copying = device !== null && !editing

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
      ...(editing && device ? { enabled: device.enabled } : {}),
    }
    try {
      const saved =
        editing && device
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
        {/* A senha fica cifrada e nunca volta pela API, então a cópia pede outra. */}
        <input className="field" type="password" value={form.password} onChange={update('password')}
          required={!editing}
          placeholder={editing ? 'manter a atual' : copying ? 'digite de novo' : undefined} />
      </label>
      <label className="device-form__field">
        Modelo
        <input className="field" value={form.model} onChange={update('model')}
          placeholder="opcional" />
      </label>
      <div className="device-form__actions">
        <button className="button button--primary" type="submit" disabled={saving}>
          {saving
            ? 'Salvando…'
            : editing
              ? 'Salvar alterações'
              : copying
                ? 'Salvar cópia'
                : 'Adicionar equipamento'}
        </button>
        <button className="button" type="button" onClick={onCancel} disabled={saving}>
          Cancelar
        </button>
        {error && <span className="row__error">{error}</span>}
      </div>
    </form>
  )
}

function Devices({
  devices,
  setDevices,
  onSynced,
}: {
  devices: Device[]
  setDevices: Dispatch<SetStateAction<Device[]>>
  onSynced: () => void
}) {
  const [syncing, setSyncing] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<FormTarget | null>(null)
  const addingNew = form?.device === null

  const saved = (device: Device) => {
    setDevices((current) =>
      current.some((item) => item.id === device.id)
        ? current.map((item) => (item.id === device.id ? device : item))
        : [...current, device],
    )
    setForm(null)
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

  /** One device at a time: they answer at very different speeds and a slow one
   *  must not hold back the others' progress being reported. */
  const syncAll = async () => {
    setMessage(null)
    setError(null)
    const total = { created: 0, updated: 0, photos: 0, removed: 0, failures: 0 }
    const problems: string[] = []
    for (const [index, device] of devices.entries()) {
      setSyncing(`${device.name} (${index + 1} de ${devices.length})`)
      try {
        const report = await sendJson<SyncReport>(`/residents/sync/${device.id}`, 'POST')
        total.created += report.created
        total.updated += report.updated
        total.photos += report.photos_downloaded
        total.removed += report.removed
        total.failures += report.failures
      } catch (failure) {
        problems.push(`${device.name}: ${(failure as Error).message}`)
      }
    }
    setSyncing(null)
    setMessage(
      `${total.created} novos, ${total.updated} atualizados, ${total.photos} fotos` +
        (total.removed ? `, ${total.removed} removidos` : '') +
        (total.failures ? `, ${total.failures} falhas` : ''),
    )
    if (problems.length) setError(problems.join(' · '))
    onSynced()
  }

  return (
    <section className="panel">
      <h2 className="panel__title">
        Equipamentos
        <button
          type="button"
          className="button button--primary panel__action"
          onClick={syncAll}
          disabled={syncing !== null || devices.length === 0}
        >
          {syncing ? `Sincronizando ${syncing}…` : 'Sincronizar cadastros'}
        </button>
        <button
          type="button"
          className="button"
          onClick={() => setForm(addingNew ? null : { device: null, editing: false })}
        >
          {addingNew ? 'Fechar' : 'Adicionar facial'}
        </button>
      </h2>
      {form && (
        <DeviceForm
          // Remonta ao trocar de alvo, para os campos partirem dele.
          key={`${form.device?.id ?? 'nova'}:${form.editing}`}
          target={form}
          onSaved={saved}
          onCancel={() => setForm(null)}
        />
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
                type="button"
                className="button"
                onClick={() => setForm({ device, editing: true })}
              >
                Editar
              </button>
              <button
                type="button"
                className="button"
                onClick={() => setForm({ device, editing: false })}
              >
                Duplicar
              </button>
              <button type="button" className="button button--danger" onClick={() => discard(device)}>
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
  const { signOut } = useAuth()
  const [residents, setResidents] = useState<Resident[]>([])
  const [devices, setDevices] = useState<Device[]>([])
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

  useEffect(() => {
    getJson<Device[]>('/devices')
      .then(setDevices)
      .catch((failure: Error) => setError(failure.message))
  }, [])

  const deviceNames = useMemo(
    () => new Map(devices.map((device) => [device.id, device.name])),
    [devices],
  )

  const people = useMemo(() => groupByPerson(residents), [residents])
  const pending = people.filter((person) => !person.apartment).length

  const visible = useMemo(() => {
    const term = normalize(search.trim())
    return people.filter((person) => {
      if (onlyPending && person.apartment) return false
      if (!term) return true
      return normalize(person.name).includes(term) || person.employee_no.includes(term)
    })
  }, [people, search, onlyPending])

  const purge = async () => {
    const confirmado = window.confirm(
      `Apagar os ${residents.length} cadastros de moradores e suas fotos?\n\n` +
        'Os apartamentos informados aqui serão perdidos. As pessoas continuam ' +
        'cadastradas nas faciais, e sincronizar traz nome e foto de volta.',
    )
    if (!confirmado) return
    setError(null)
    try {
      await remove('/residents')
      setResidents([])
    } catch (failure) {
      setError((failure as Error).message)
    }
  }

  const replace = (saved: Resident[]) =>
    setResidents((current) =>
      current.map((resident) => saved.find((item) => item.id === resident.id) ?? resident),
    )

  return (
    <main className="admin">
      <header className="admin__header">
        <h1 className="admin__title">Administração</h1>
        <ThemeToggle />
        <Link className="button" to="/">
          Ver tela da portaria
        </Link>
        <button type="button" className="button" onClick={signOut}>
          Sair
        </button>
      </header>

      <Devices devices={devices} setDevices={setDevices} onSynced={load} />

      <section className="panel">
        <h2 className="panel__title">
          Moradores
          <span className="panel__count">
            {people.length} pessoas · {residents.length} cadastros nas faciais ·{' '}
            {pending} sem apartamento
          </span>
          <button
            type="button"
            className="button button--danger panel__action"
            onClick={purge}
            disabled={residents.length === 0}
          >
            Limpar cadastros
          </button>
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
                  <th>Faciais</th>
                  <th>Apartamento</th>
                  <th>Bloco</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((person) => (
                  <ResidentRow
                    key={person.key}
                    person={person}
                    deviceNames={deviceNames}
                    onSaved={replace}
                  />
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
