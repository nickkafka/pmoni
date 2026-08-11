<#
.SYNOPSIS
    Gera o instalador do pMoni.

.DESCRIPTION
    As tres etapas se alimentam em ordem, e nenhuma delas reclama sozinha se a
    anterior nao rodou: o PyInstaller embute a interface que o Vite acabou de
    construir, e o electron-builder embute o executavel que o PyInstaller acabou de
    gerar. Rodar fora de ordem produz um instalador com uma versao antiga dentro.

.PARAMETER SkipInstall
    Nao reinstala as dependencias. Util para repetir o build na mesma maquina.

.EXAMPLE
    .\installer\build.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Ambiente virtual nao encontrado em $python. Crie com 'python -m venv .venv' no diretorio backend."
}

Write-Host "==> 1/3 Construindo a interface" -ForegroundColor Cyan
Push-Location $frontend
try {
    if (-not $SkipInstall) {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install falhou." }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build falhou." }
}
finally { Pop-Location }

Write-Host "==> 2/3 Empacotando o backend" -ForegroundColor Cyan
Push-Location $backend
try {
    if (-not $SkipInstall) {
        & $python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw "pip install falhou." }
    }
    & $python -m PyInstaller --noconfirm --clean pmoni.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }
}
finally { Pop-Location }

# O empacotamento acontece fora da pasta do projeto de proposito. O electron-builder
# extrai o Electron para 'win-unpacked.tmp' e renomeia o diretorio para
# 'win-unpacked'; dentro de uma arvore sincronizada pelo OneDrive esse rename volta
# 'acesso negado' — o filtro de arquivos do OneDrive continua ativo mesmo com o
# aplicativo fechado, e apagar o diretorio funciona enquanto renomear nao. Copiar o
# instalador pronto de volta e uma escrita de arquivo comum, que passa sem problema.
$staging = Join-Path $env:LOCALAPPDATA "pMoni-build"
$release = Join-Path $frontend "release"

Write-Host "==> 3/3 Gerando o instalador" -ForegroundColor Cyan
Push-Location $frontend
try {
    npm run installer -- --config.directories.output="$staging"
    if ($LASTEXITCODE -ne 0) { throw "electron-builder falhou." }
}
finally { Pop-Location }

$installer = Get-ChildItem $staging -Filter "*.exe" |
    Where-Object { $_.Name -notlike "*uninstaller*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $installer) { throw "electron-builder terminou sem gerar um instalador em $staging." }

New-Item -ItemType Directory -Force -Path $release | Out-Null
Copy-Item $installer.FullName $release -Force

Write-Host ""
Write-Host "Instalador gerado: $(Join-Path $release $installer.Name)" -ForegroundColor Green
