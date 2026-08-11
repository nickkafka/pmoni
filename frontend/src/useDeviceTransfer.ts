import { useRef, useState } from 'react'
import { getJson, sendJson } from './api'
import type { DeviceExport, DeviceImportReport, PendingDevice } from './types'

function reportOf(report: DeviceImportReport): string | null {
  const parts: string[] = []
  if (report.created) parts.push(`${report.created} cadastrado(s)`)
  if (report.updated) parts.push(`${report.updated} atualizado(s)`)
  return parts.length > 0 ? `${parts.join(', ')}.` : null
}

/**
 * Taking the equipment configuration out to a file and back in.
 *
 * The state lives in a hook because the controls belong in the panel heading, next
 * to the other actions, while what they have to say belongs in the panel body —
 * two places in the markup, one piece of state.
 */
export function useDeviceTransfer(onImported: () => void) {
  const file = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  /** Equipamentos aguardando senha, que o pop-up pede antes de cadastrá-los. */
  const [pending, setPending] = useState<PendingDevice[]>([])

  const clear = () => {
    setMessage(null)
    setError(null)
  }

  const exportDevices = async () => {
    clear()
    setBusy(true)
    try {
      const payload = await getJson<DeviceExport>('/devices/export')
      // Montado a partir do JSON já em memória, e não como link para a rota: ela
      // exige a sessão, que um link comum não carregaria.
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }),
      )
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `pmoni-faciais-${new Date().toISOString().slice(0, 10)}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      setMessage(
        `${payload.devices.length} equipamento(s) exportado(s). O arquivo não contém senhas.`,
      )
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const send = async (devices: unknown): Promise<DeviceImportReport | null> => {
    clear()
    setBusy(true)
    try {
      const report = await sendJson<DeviceImportReport>('/devices/import', 'POST', devices)
      const done = reportOf(report)
      if (done) {
        setMessage(done)
        onImported()
      }
      setPending(report.pending)
      return report
    } catch (failure) {
      const reason = failure as Error
      setError(reason instanceof SyntaxError ? 'O arquivo não é um JSON válido.' : reason.message)
      return null
    } finally {
      setBusy(false)
    }
  }

  const importFile = async (chosen: File) => {
    let parsed: unknown
    try {
      parsed = JSON.parse(await chosen.text())
    } catch {
      clear()
      setError('O arquivo não é um JSON válido.')
      return
    } finally {
      // Deixa escolher o mesmo arquivo outra vez, depois de corrigido.
      if (file.current) file.current.value = ''
    }
    await send(parsed)
  }

  /** Reenvia os pendentes com as senhas que o operador acabou de digitar. */
  const registerPending = async (passwords: Record<string, string>) => {
    const completed = pending.map((device) => ({
      ...device,
      password: passwords[keyOf(device)],
    }))
    const report = await send(completed)
    if (report && report.pending.length === 0) setPending([])
  }

  const dismissPending = () => {
    setPending([])
    setMessage(null)
  }

  return {
    file, busy, message, error, pending,
    exportDevices, importFile, registerPending, dismissPending,
  }
}

/** Endereço e porta: o par que identifica um equipamento antes de ele ter id. */
export function keyOf(device: PendingDevice): string {
  return `${device.host}:${device.port}`
}

export type DeviceTransferControls = ReturnType<typeof useDeviceTransfer>
