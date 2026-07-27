export type ResidentMessage = {
  id: number
  employee_no: string
  name: string
  apartment: string | null
  block: string | null
  photo_url: string | null
}

export type AccessEventMessage = {
  external_id: string
  device_id: number
  employee_no: string | null
  access_type: string
  success: boolean
  event_time: string
  snapshot: string | null
  resident: ResidentMessage | null
}

/** `unavailable` means the backend is up but has no monitoring configured. */
export type ConnectionStatus = 'connecting' | 'connected' | 'offline' | 'unavailable'
