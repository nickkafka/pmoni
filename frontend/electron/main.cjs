/**
 * The window that wraps the application.
 *
 * There is no server to point at: the backend runs on this same machine, started
 * here as a child process and stopped when the window closes. The window then loads
 * it over http rather than reading the built files from disk, because the interface
 * addresses the API by relative paths and builds its WebSocket address from
 * `window.location.host` — under `file://` there is no host and neither would work.
 */

const { app, BrowserWindow, dialog, shell } = require('electron')
const { spawn } = require('node:child_process')
const net = require('node:net')
const os = require('node:os')
const path = require('node:path')

const HOST = '127.0.0.1'
const PREFERRED_PORT = 8000

/** Mirrors where the backend keeps its data, so we can point at its log. */
const DATA_DIRECTORY = path.join(
  process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'),
  'pMoni',
)

/** How long the backend gets to answer before we give up and say so. */
const STARTUP_TIMEOUT_MS = 60000
const STARTUP_RETRY_MS = 250

let backend = null
let backendExited = null

function backendExecutable() {
  const name = 'pmoni-backend.exe'
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend', name)
  }
  return path.join(__dirname, '..', '..', 'backend', 'dist', 'pmoni-backend', name)
}

/**
 * 8000 is a popular port, and on a machine where something already answers there
 * the application would fail to start with nothing on screen to explain it. Any
 * free port does just as well, since only this window ever connects.
 */
function choosePort() {
  return new Promise((resolve) => {
    const probe = net.createServer()
    probe.once('error', () => resolve(0))
    probe.listen(PREFERRED_PORT, HOST, () => {
      probe.close(() => resolve(PREFERRED_PORT))
    })
  }).then((port) => (port ? port : freePort()))
}

function freePort() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer()
    probe.once('error', reject)
    probe.listen(0, HOST, () => {
      const { port } = probe.address()
      probe.close(() => resolve(port))
    })
  })
}

function startBackend(port) {
  backend = spawn(backendExecutable(), [], {
    env: {
      ...process.env,
      API_HOST: HOST,
      API_PORT: String(port),
      // Lets it stop on its own if this process dies without getting to kill it.
      PMONI_PARENT_PID: String(process.pid),
    },
    // It is a console program so it still has somewhere to write its output. This
    // keeps the console from showing up on screen.
    windowsHide: true,
    stdio: 'ignore',
  })

  backendExited = new Promise((resolve) => {
    backend.once('exit', (code) => resolve(code))
    backend.once('error', () => resolve(-1))
  })
}

async function waitForBackend(port) {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS
  let settled = false
  backendExited.then(() => {
    settled = true
  })

  while (Date.now() < deadline) {
    // A backend that died is never going to answer, and waiting out the full
    // timeout would only delay the message explaining what happened.
    if (settled) return false
    try {
      const response = await fetch(`http://${HOST}:${port}/health`)
      if (response.ok) return true
    } catch {
      // Not listening yet.
    }
    await new Promise((resolve) => setTimeout(resolve, STARTUP_RETRY_MS))
  }
  return false
}

function createWindow(port) {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    autoHideMenuBar: true,
    title: 'pMoni',
    webPreferences: {
      // The page is our own build and needs nothing from Node.
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  window.maximize()
  window.once('ready-to-show', () => window.show())

  // A photo or a link opened from inside the interface belongs in the browser, not
  // in a second window with no way back.
  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  window.loadURL(`http://${HOST}:${port}/`)
  return window
}

function stopBackend() {
  if (backend && backend.exitCode === null) {
    backend.kill()
  }
  backend = null
}

// Two copies would each start their own backend and their own window over the same
// database. The second one just surfaces the window that is already open.
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    const [window] = BrowserWindow.getAllWindows()
    if (window) {
      if (window.isMinimized()) window.restore()
      window.focus()
    }
  })

  app.whenReady().then(async () => {
    const port = await choosePort()
    startBackend(port)

    if (await waitForBackend(port)) {
      createWindow(port)
      return
    }

    stopBackend()
    dialog.showErrorBox(
      'pMoni',
      'O serviço do pMoni não iniciou. O motivo está registrado em\n' +
        path.join(DATA_DIRECTORY, 'logs', 'pmoni.log'),
    )
    app.quit()
  })

  app.on('window-all-closed', () => {
    stopBackend()
    app.quit()
  })

  // Closing the window is not the only way out: a shutdown or a kill of this
  // process would otherwise leave the backend running with no window.
  app.on('before-quit', stopBackend)
}
