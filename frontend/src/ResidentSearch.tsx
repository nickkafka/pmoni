import { useEffect, useRef, useState } from 'react'
import { photoUrl } from './api'
import type { DirectoryPerson } from './types'
import { MINIMUM_QUERY, type ResidentSearchControls } from './useResidentSearch'
import './ResidentSearch.css'

export function SearchField({ search }: { search: ResidentSearchControls }) {
  const field = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // The booth has no mouse in reach half the time. Escape leaves the search, and
    // any other typing on the bare screen goes into it, so the porter can simply
    // start typing a name.
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        search.clear()
        field.current?.blur()
        return
      }
      const target = event.target as HTMLElement | null
      const editing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')
      if (editing || event.ctrlKey || event.altKey || event.metaKey) return
      if (event.key.length === 1) field.current?.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [search])

  return (
    <div className="search">
      <SearchIcon />
      <input
        ref={field}
        className="search__field"
        type="search"
        value={search.query}
        placeholder="Nome, documento ou -apartamento"
        aria-label="Procurar morador por nome, documento ou apartamento"
        onChange={(event) => search.setQuery(event.target.value)}
      />
      {search.query && (
        <button type="button" className="search__clear" onClick={search.clear} aria-label="Limpar busca">
          ×
        </button>
      )}
      <SearchHelp />
    </div>
  )
}

/** Explains the dash, which nobody would guess at from an empty field. */
function SearchHelp() {
  return (
    <span
      className="search__help"
      tabIndex={0}
      role="note"
      aria-label="Como pesquisar apartamento e bloco"
    >
      i
      <span className="search__bubble">
        <strong className="search__bubble-title">Como pesquisar</strong>
        <dl className="search__examples">
          <dt>joão</dt>
          <dd>procura pelo nome</dd>
          <dt>123.456.789-00</dt>
          <dd>procura pelo documento, com ou sem pontos</dd>
          <dt>
            <b>-</b>301
          </dt>
          <dd>apartamento 301</dd>
          <dt>
            <b>-</b>A
          </dt>
          <dd>bloco A</dd>
        </dl>
        <span className="search__bubble-note">
          O traço diz que o número é um apartamento ou bloco. Sem ele, um número curto
          se confunde com pedaços de documento — e apartamentos de um dígito, como o
          1, nem seriam procurados.
        </span>
      </span>
    </span>
  )
}

function SearchIcon() {
  return (
    <svg className="search__icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
      <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function PersonPhoto({ person }: { person: DirectoryPerson }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [person.photo_id])

  if (person.photo_id === null || failed) {
    return <div className="found__photo found__photo--empty" aria-hidden="true" />
  }
  return (
    <img
      className="found__photo"
      src={photoUrl(person.photo_id)}
      alt={person.name}
      onError={() => setFailed(true)}
    />
  )
}

function locationOf(person: DirectoryPerson): string | null {
  if (!person.apartment) return null
  return person.block ? `Apto ${person.apartment} · Bloco ${person.block}` : `Apto ${person.apartment}`
}

/**
 * Almost everyone is enrolled on every gate, so spelling the list out buries the
 * name and the apartment under seven lines of equipment names — and answers a
 * question the porter did not ask. Naming them only stays useful while there are
 * few, which is exactly the case worth noticing: someone who cannot enter here.
 */
const NAMES_WORTH_SPELLING = 2

function enrolmentSummary(person: DirectoryPerson): string {
  const total = person.device_ids.length
  if (person.device_names.length > 0 && person.device_names.length <= NAMES_WORTH_SPELLING) {
    return person.device_names.join(' · ')
  }
  return total === 1 ? '1 facial' : `${total} faciais`
}

export function SearchResults({ search }: { search: ResidentSearchControls }) {
  const { trimmed, results, searching, failed } = search
  // Com o traço basta um caractere: ele já disse que o que vem é apartamento ou
  // bloco, e há apartamentos de um dígito.
  const byLocation = trimmed.startsWith('-')
  const short = trimmed.length < (byLocation ? 2 : MINIMUM_QUERY)

  return (
    <aside className="results" aria-live="polite">
      <header className="results__header">
        <span className="label-caps">Consulta de morador</span>
        <span className="results__count">
          {short ? '' : searching ? 'procurando…' : `${results.length} encontrado(s)`}
        </span>
      </header>

      {short ? (
        <p className="results__empty">
          {byLocation
            ? 'Digite o apartamento ou o bloco depois do traço.'
            : `Digite ao menos ${MINIMUM_QUERY} caracteres.`}
        </p>
      ) : failed ? (
        <p className="results__empty">Não foi possível consultar o cadastro.</p>
      ) : results.length === 0 && !searching ? (
        <p className="results__empty">Ninguém encontrado para “{trimmed}”.</p>
      ) : (
        <ul className="results__list">
          {results.map((person) => (
            <li className="found" key={`${person.employee_no}:${person.name}`}>
              <PersonPhoto person={person} />
              <div className="found__about">
                <p className="found__name">{person.name}</p>
                {locationOf(person) ? (
                  <p className="found__location">{locationOf(person)}</p>
                ) : (
                  <p className="found__location found__location--missing">Apartamento não cadastrado</p>
                )}
                {person.document && <p className="found__document">{person.document}</p>}
                <p className="found__devices" title={person.device_names.join(' · ')}>
                  {enrolmentSummary(person)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
