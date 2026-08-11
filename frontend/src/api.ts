let authToken: string | null = null
let onUnauthorized: (() => void) | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

/** Lets the interface lock itself again when a session expires mid-use. */
export function onSessionLost(handler: (() => void) | null): void {
  onUnauthorized = handler
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  return authToken ? { ...extra, Authorization: `Bearer ${authToken}` } : extra
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    if (response.status === 401) {
      authToken = null
      onUnauthorized?.()
    }
    const detail = await response
      .json()
      .then((body) => body?.detail)
      .catch(() => null)
    throw new Error(typeof detail === 'string' ? detail : `Falha na requisição (${response.status}).`)
  }
  return response.json() as Promise<T>
}

export function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return fetch(path, { headers: headers(), signal }).then((response) => parse<T>(response))
}

export function sendJson<T>(path: string, method: 'POST' | 'PUT' | 'PATCH', body?: unknown): Promise<T> {
  return fetch(path, {
    method,
    headers: headers({ 'Content-Type': 'application/json' }),
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((response) => parse<T>(response))
}

export async function remove(path: string): Promise<void> {
  const response = await fetch(path, { method: 'DELETE', headers: headers() })
  if (!response.ok) {
    if (response.status === 401) {
      authToken = null
      onUnauthorized?.()
    }
    const detail = await response
      .json()
      .then((body) => body?.detail)
      .catch(() => null)
    throw new Error(typeof detail === 'string' ? detail : `Falha ao excluir (${response.status}).`)
  }
}

export function photoUrl(residentId: number): string {
  return `/residents/${residentId}/photo`
}
