export type ResidentMessage = {
  id: number
  employee_no: string
  name: string
  apartment: string | null
  block: string | null
  photo_url: string | null
}

export type DeviceMessage = {
  id: number
  name: string
}

export type AccessEventMessage = {
  external_id: string
  device_id: number
  employee_no: string | null
  access_type: string
  success: boolean
  event_time: string
  /** Capture taken at the passage, served by the backend when the device took one. */
  snapshot_url: string | null
  resident: ResidentMessage | null
  device: DeviceMessage | null
}

/** `unavailable` means the backend is up but has no monitoring configured. */
export type ConnectionStatus = 'connecting' | 'connected' | 'offline' | 'unavailable'

export type Resident = {
  id: number
  /** Enrollments are issued per device: the ID alone does not name a person. */
  device_id: number
  employee_no: string
  name: string
  apartment: string | null
  block: string | null
  has_photo: boolean
  synced_at: string | null
}

export type Device = {
  id: number
  name: string
  host: string
  port: number
  username: string
  model: string | null
  enabled: boolean
}

export type SyncReport = {
  created: number
  updated: number
  photos_downloaded: number
  failures: number
}
