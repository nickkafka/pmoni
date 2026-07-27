async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => body?.detail)
      .catch(() => null)
    throw new Error(typeof detail === 'string' ? detail : `Falha na requisição (${response.status}).`)
  }
  return response.json() as Promise<T>
}

export function getJson<T>(path: string): Promise<T> {
  return fetch(path).then((response) => parse<T>(response))
}

export function sendJson<T>(path: string, method: 'POST' | 'PATCH', body?: unknown): Promise<T> {
  return fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((response) => parse<T>(response))
}

export async function remove(path: string): Promise<void> {
  const response = await fetch(path, { method: 'DELETE' })
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => body?.detail)
      .catch(() => null)
    throw new Error(typeof detail === 'string' ? detail : `Falha ao excluir (${response.status}).`)
  }
}

export function photoUrl(employeeNo: string): string {
  return `/residents/${encodeURIComponent(employeeNo)}/photo`
}
