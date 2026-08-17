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
  /** Vêm do Sigma, ou são digitados para quem o Sigma não conhece. */
  cpf: string | null
  rg: string | null
  has_photo: boolean
  synced_at: string | null
}

export type SigmaIntegration = {
  /** Há um token guardado. O valor dele nunca chega até aqui. */
  configured: boolean
  account_id: number | null
  last_import_at: string | null
  last_status: ImportStatus | null
  last_message: string | null
}

export type SigmaAccount = {
  id: number
  name: string | null
  code: string | null
}

export type SigmaImportResult = {
  status: ImportStatus
  message: string
  read: number
  updated: number
  /** Estão no Sigma e não casaram com nenhuma facial. */
  unmatched: string[]
}

/** A person as the porter's search returns them, gathered from every enrollment. */
export type DirectoryPerson = {
  employee_no: string
  name: string
  apartment: string | null
  block: string | null
  cpf: string | null
  rg: string | null
  /** Enrollment holding the picture, which may belong to another device. */
  photo_id: number | null
  device_ids: number[]
  device_names: string[]
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

export type DeviceExport = {
  exported_at: string
  devices: Omit<Device, 'id'>[]
  note: string
}

/** Equipamento do arquivo que ainda não foi cadastrado por faltar a senha. */
export type PendingDevice = Omit<Device, 'id'>

export type DeviceImportReport = {
  created: number
  updated: number
  pending: PendingDevice[]
}

/** `partial` = importou, mas alguma facial não respondeu. */
export type ImportStatus = 'ok' | 'partial' | 'failed'

export type ImportAutomation = {
  enabled: boolean
  /** "HH:MM" na hora local da portaria. */
  run_at: string
  last_run_at: string | null
  last_status: ImportStatus | null
  last_message: string | null
}

export type SyncReport = {
  created: number
  updated: number
  photos_downloaded: number
  removed: number
  /** Pessoas cujo rosto a facial guarda só como template, sem imagem. */
  without_photo: number
  failures: number
}
