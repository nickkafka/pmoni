import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAccessEventStream } from './accessEventsContext'
import { SearchField, SearchResults } from './ResidentSearch'
import { ThemeToggle } from './ThemeToggle'
import { useResidentSearch } from './useResidentSearch'
import type { AccessEventMessage, ConnectionStatus } from './types'
import './PorterScreen.css'

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  connecting: 'Conectando',
  connected: 'Monitorando',
  offline: 'Sem conexão',
  unavailable: 'Monitoramento não configurado',
}

function timeOf(event: AccessEventMessage): string {
  return new Date(event.event_time).toLocaleTimeString('pt-BR')
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/)
  const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : parts
  return letters.map((part) => part[0]?.toUpperCase() ?? '').join('')
}

function deviceOf(event: AccessEventMessage): string {
  return event.device?.name ?? `Equipamento ${event.device_id}`
}

function locationOf(event: AccessEventMessage): string | null {
  const resident = event.resident
  if (!resident?.apartment) return null
  return resident.block ? `Apto ${resident.apartment} · Bloco ${resident.block}` : `Apto ${resident.apartment}`
}

function isInactive(event: AccessEventMessage): boolean {
  return event.resident?.active === false
}

function Photo({
  event,
  size,
}: {
  event: AccessEventMessage
  size: 'large' | 'small' | 'preview'
}) {
  const resident = event.resident
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [resident?.photo_url])

  if (resident?.photo_url && !failed) {
    return (
      <img
        className={`photo photo--${size}`}
        src={resident.photo_url}
        alt={resident.name}
        onError={() => setFailed(true)}
      />
    )
  }
  return (
    <div className={`photo photo--${size} photo--empty`} aria-hidden="true">
      {resident ? initialsOf(resident.name) : '?'}
    </div>
  )
}

/** Renders nothing once the capture is gone: the store only keeps recent ones. */
function Capture({
  url,
  size,
  caption,
}: {
  url: string
  size: 'large' | 'preview'
  caption?: string
}) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  if (failed) return null

  const image = (
    <img
      className={`photo photo--${size} photo--capture`}
      src={url}
      alt="Imagem capturada na passagem"
      onError={() => setFailed(true)}
    />
  )
  if (!caption) return image
  return (
    <figure className="shot">
      {image}
      <figcaption className="shot__caption">{caption}</figcaption>
    </figure>
  )
}

function CurrentEvent({ event }: { event: AccessEventMessage }) {
  const resident = event.resident
  const location = locationOf(event)
  return (
    <section className={`current current--${event.success ? 'granted' : 'denied'}`}>
      <div className={`current__photos${event.snapshot_url ? ' current__photos--paired' : ''}`}>
        <figure className="shot">
          <Photo event={event} size="large" />
          <figcaption className="shot__caption">Cadastro</figcaption>
        </figure>
        {event.snapshot_url && (
          <Capture url={event.snapshot_url} size="large" caption="Agora" />
        )}
      </div>
      <div className="current__details">
        <h1 className="current__name">{resident?.name ?? 'Não cadastrado'}</h1>
        {location ? (
          <p className="current__location">{location}</p>
        ) : (
          <p className="current__location current__location--missing">
            {resident ? 'Apartamento não cadastrado' : `ID ${event.employee_no ?? '—'}`}
          </p>
        )}
        <p className="current__badges">
          <span className={`current__verdict current__verdict--${event.success ? 'granted' : 'denied'}`}>
            {event.success ? 'Acesso liberado' : 'Acesso negado'}
          </span>
          <span className="current__device">{deviceOf(event)}</span>
          {isInactive(event) && (
            <span className="inactive-tag current__inactive">Inativo no Sigma</span>
          )}
        </p>
        <p className="current__meta">
          {timeOf(event)}
          {resident ? ` · ID ${resident.employee_no}` : ''}
        </p>
      </div>
    </section>
  )
}

/** Acompanha a largura de `.preview` no CSS, que posiciona o card na tela. */
const PREVIEW_WIDTH = 544
const PREVIEW_GAP = 12

type PreviewAt = { event: AccessEventMessage; left: number; bottom: number }

function Preview({ at }: { at: PreviewAt }) {
  const { event } = at
  const resident = event.resident
  const location = locationOf(event)
  const card = useRef<HTMLElement>(null)
  const [bottom, setBottom] = useState(at.bottom)

  // Anchored above the strip, the card grows upward — and since it was enlarged it
  // no longer always fits there. Measured after rendering, because its height
  // depends on how far the name wraps, and slid down when the top would be cut off:
  // covering part of the strip still shows the face, while running off the screen
  // hides exactly what the porter opened it to see.
  useLayoutEffect(() => {
    const height = card.current?.offsetHeight ?? 0
    const highest = window.innerHeight - height - PREVIEW_GAP
    setBottom(Math.min(at.bottom, Math.max(PREVIEW_GAP, highest)))
  }, [at])

  return (
    <aside className="preview" ref={card} style={{ left: at.left, bottom }}>
      <div className="preview__photos">
        <figure className="shot">
          <Photo event={event} size="preview" />
          <figcaption className="shot__caption">Cadastro</figcaption>
        </figure>
        {event.snapshot_url && (
          <Capture url={event.snapshot_url} size="preview" caption="Agora" />
        )}
      </div>
      <p className="preview__name">{resident?.name ?? 'Não cadastrado'}</p>
      {isInactive(event) && <span className="inactive-tag preview__inactive">Inativo no Sigma</span>}
      <p className={`preview__location${location ? '' : ' preview__location--missing'}`}>
        {location ?? (resident ? 'Apartamento não cadastrado' : `ID ${event.employee_no ?? '—'}`)}
      </p>
      <p className="preview__meta">
        {timeOf(event)} · {deviceOf(event)}
      </p>
    </aside>
  )
}

function History({ events }: { events: AccessEventMessage[] }) {
  const [preview, setPreview] = useState<PreviewAt | null>(null)
  if (events.length === 0) return null

  // Anchored above the strip, which sits at the bottom of the screen, and kept
  // inside the viewport so the first and last entries stay readable.
  const show = (event: AccessEventMessage) => (pointer: ReactMouseEvent<HTMLLIElement>) => {
    const anchor = pointer.currentTarget.getBoundingClientRect()
    const centred = anchor.left + anchor.width / 2 - PREVIEW_WIDTH / 2
    setPreview({
      event,
      left: Math.max(PREVIEW_GAP, Math.min(centred, window.innerWidth - PREVIEW_WIDTH - PREVIEW_GAP)),
      bottom: window.innerHeight - anchor.top + PREVIEW_GAP,
    })
  }

  return (
    <footer className="history">
      <span className="label-caps">Anteriores</span>
      <ul className="history__list">
        {events.map((event) => (
          <li
            key={keyOf(event)}
            className="history__item"
            onMouseEnter={show(event)}
            onMouseLeave={() => setPreview(null)}
          >
            <Photo event={event} size="small" />
            <span className="history__name">{event.resident?.name ?? 'Não cadastrado'}</span>
            {isInactive(event) && <span className="inactive-tag history__inactive">Inativo</span>}
            <span className="history__device">{deviceOf(event)}</span>
            <span className="history__time">{timeOf(event)}</span>
          </li>
        ))}
      </ul>
      {preview && <Preview at={preview} />}
    </footer>
  )
}

/** Cai para o nome escrito se o arquivo do logo não estiver publicado. */
function Brand() {
  const [missing, setMissing] = useState(false)
  if (missing) return <span className="header__brand">pMoni</span>
  return (
    <img
      className="header__logo"
      src="/logo.png"
      alt="Grupo Prever"
      onError={() => setMissing(true)}
    />
  )
}

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return <time className="header__clock">{now.toLocaleTimeString('pt-BR')}</time>
}

/**
 * Quanto tempo a passagem fica em destaque antes de descer para a faixa.
 *
 * A foto grande serve para o porteiro conferir quem acabou de passar; deixada na
 * tela até a próxima passagem, ela fica exposta por minutos a quem estiver na
 * guarita. Depois disso a pessoa segue na faixa, onde o hover ainda a amplia.
 */
const CURRENT_SECONDS = 10

function keyOf(event: AccessEventMessage): string {
  return `${event.device_id}:${event.external_id}`
}

/**
 * Whether the latest passage is still inside its moment on screen.
 *
 * Timed from when it reached this screen rather than from `event_time`: the facial's
 * clock is not this machine's, and a few seconds of drift would hide a passage
 * before the porter ever saw it.
 */
function useFresh(latest: AccessEventMessage | undefined): boolean {
  const key = latest ? keyOf(latest) : null
  const [expired, setExpired] = useState<string | null>(null)

  useEffect(() => {
    if (key === null) return
    const timer = window.setTimeout(() => setExpired(key), CURRENT_SECONDS * 1000)
    return () => window.clearTimeout(timer)
  }, [key])

  return key !== null && key !== expired
}

export default function PorterScreen() {
  const { events, status } = useAccessEventStream()
  const [latest] = events
  const fresh = useFresh(latest)
  const current = fresh ? latest : undefined
  const previous = fresh ? events.slice(1) : events
  const search = useResidentSearch()

  return (
    <main className={`porter${search.open ? ' porter--searching' : ''}`}>
      <header className="header">
        <Brand />
        <SearchField search={search} />
        <span className={`header__status header__status--${status}`}>
          <span className="header__dot" aria-hidden="true" />
          {STATUS_LABEL[status]}
        </span>
        <Clock />
        <ThemeToggle />
        <Link className="header__admin" to="/admin">
          Administração
        </Link>
      </header>

      {current ? (
        <CurrentEvent event={current} />
      ) : (
        <section className="waiting">
          <p className="waiting__title">Aguardando movimento</p>
          <p className="waiting__hint">
            {latest
              ? 'A última passagem está na faixa abaixo. A próxima aparece aqui.'
              : 'A próxima pessoa que passar na facial aparece aqui.'}
          </p>
        </section>
      )}

      <History events={previous} />

      {search.open && <SearchResults search={search} />}
    </main>
  )
}
