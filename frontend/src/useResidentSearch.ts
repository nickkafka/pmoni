import { useEffect, useState } from 'react'
import { getJson } from './api'
import type { DirectoryPerson } from './types'

/** Matches the backend: anything shorter answers with most of the building. */
export const MINIMUM_QUERY = 2

/** Long enough that typing a name is one request, short enough to feel immediate. */
const DEBOUNCE_MS = 250

type SearchState = {
  query: string
  results: DirectoryPerson[]
  searching: boolean
  failed: boolean
  /** Open from the first character, so the panel does not appear mid-word. */
  open: boolean
}

/**
 * Looking a resident up while the passages keep arriving.
 *
 * The porter types with someone waiting in front of them, so every keystroke would
 * otherwise be a request and the answers could arrive out of order — an older,
 * slower one landing last and replacing the right list. Debouncing cuts the
 * requests down and the abort makes a superseded one unable to report at all.
 */
export function useResidentSearch() {
  const [state, setState] = useState<SearchState>({
    query: '',
    results: [],
    searching: false,
    failed: false,
    open: false,
  })

  const trimmed = state.query.trim()

  useEffect(() => {
    if (trimmed.length < MINIMUM_QUERY) {
      setState((current) => ({ ...current, results: [], searching: false, failed: false }))
      return
    }

    const controller = new AbortController()
    setState((current) => ({ ...current, searching: true }))

    const timer = window.setTimeout(() => {
      getJson<DirectoryPerson[]>(
        `/residents/search?q=${encodeURIComponent(trimmed)}`,
        controller.signal,
      )
        .then((results) =>
          setState((current) => ({ ...current, results, searching: false, failed: false })),
        )
        .catch((error) => {
          if (controller.signal.aborted) return
          console.error(error)
          setState((current) => ({ ...current, results: [], searching: false, failed: true }))
        })
    }, DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [trimmed])

  const setQuery = (value: string) =>
    setState((current) => ({ ...current, query: value, open: value.trim().length > 0 }))

  const clear = () =>
    setState({ query: '', results: [], searching: false, failed: false, open: false })

  return { ...state, trimmed, setQuery, clear }
}

export type ResidentSearchControls = ReturnType<typeof useResidentSearch>
