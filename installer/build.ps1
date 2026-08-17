<#
.SYNOPSIS
    Gera o instalador do pMoni, subindo a versao.

.DESCRIPTION
    As tres etapas se alimentam em ordem, e nenhuma delas reclama sozinha se a
    anterior nao rodou: o PyInstaller embute a interface que o Vite acabou de
    construir, e o electron-builder embute o executavel que o PyInstaller acabou de
    gerar. Rodar fora de ordem produz um instalador com uma versao antiga dentro.

    Todo build sobe a versao antes de comecar. Dois instaladores diferentes com o
    mesmo numero ja custaram uma tarde: nao havia como saber, olhando a maquina do
    cliente, se ela estava atualizada, nem pelo nome do arquivo, nem pelo painel do
    Windows, nem pela rota /health. O numero e a unica coisa que responde isso.

    A versao vive em dois lugares, porque sao duas linguagens: o package.json manda
    no nome do instalador e no que o Windows exibe, e o config.py no que a aplicacao
    responde. O script escreve os dois e confere que ficaram iguais; separados, iam
    divergir no primeiro build feito com pressa.

    Nada de acentos neste arquivo. O PowerShell 5.1 le um .ps1 sem BOM como ANSI, e
    um caractere fora do ASCII vira lixo que inclui aspas tipograficas, que ele
    aceita como delimitador de string, quebrando o script longe de onde esta o erro.

.PARAMETER SkipInstall
    Nao reinstala as dependencias. Util para repetir o build na mesma maquina.

.PARAMETER Version
    Numero exato a gravar, para uma entrega com significado. Sem isto, sobe o patch.

.PARAMETER KeepVersion
    Repete o build sem mexer na versao, para quando o anterior falhou no meio e o
    numero ja tinha sido gravado.

.EXAMPLE
    .\installer\build.ps1 -SkipInstall

.EXAMPLE
    .\installer\build.ps1 -Version 1.0.0
#>
[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,
    [switch]$KeepVersion
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$settings = Join-Path $backend "app\core\config.py"

if (-not (Test-Path $python)) {
    throw "Ambiente virtual nao encontrado em $python. Crie com 'python -m venv .venv' no diretorio backend."
}

function Get-PackageVersion {
    (Get-Content (Join-Path $frontend "package.json") -Raw -Encoding UTF8 | ConvertFrom-Json).version
}

function Get-SettingsVersion {
    $found = [regex]::Match((Get-Content $settings -Raw -Encoding UTF8), 'VERSION:\s*str\s*=\s*"([^"]*)"')
    if (-not $found.Success) { throw "Nao encontrei VERSION em $settings." }
    $found.Groups[1].Value
}

function Set-SettingsVersion([string]$novo) {
    $texto = Get-Content $settings -Raw -Encoding UTF8
    $texto = [regex]::Replace($texto, '(VERSION:\s*str\s*=\s*")[^"]*(")', "`${1}$novo`${2}")
    # Sem BOM: o arquivo e lido como codigo Python, e um BOM no inicio quebra a leitura.
    [System.IO.File]::WriteAllText($settings, $texto, (New-Object System.Text.UTF8Encoding $false))
}

Write-Host "==> 0/3 Versao" -ForegroundColor Cyan
$atual = Get-PackageVersion

if ($KeepVersion) {
    $alvo = $atual
    Write-Host "    mantida em $alvo"
}
else {
    if ($Version) {
        $alvo = $Version
    }
    else {
        $partes = $atual.Split('.')
        $alvo = "{0}.{1}.{2}" -f $partes[0], $partes[1], ([int]$partes[2] + 1)
    }
    Push-Location $frontend
    try {
        # `npm version` mantem o package-lock.json em dia junto, o que uma substituicao
        # de texto no package.json sozinha nao faria.
        npm version $alvo --no-git-tag-version --allow-same-version | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "npm version falhou." }
    }
    finally { Pop-Location }
    Set-SettingsVersion $alvo
    Write-Host "    $atual -> $alvo"
}

$noPacote = Get-PackageVersion
$noBackend = Get-SettingsVersion
if ($noPacote -ne $alvo -or $noBackend -ne $alvo) {
    throw "Versoes divergentes: package.json=$noPacote, config.py=$noBackend, esperado=$alvo."
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
# 'acesso negado': o filtro de arquivos do OneDrive continua ativo mesmo com o
# aplicativo fechado, e apagar o diretorio funciona enquanto renomear nao. Copiar o
# instalador pronto de volta e uma escrita de arquivo comum, que passa sem problema.
$staging = Join-Path $env:LOCALAPPDATA "pMoni-build"
$release = Join-Path $frontend "release"

Write-Host "==> 3/3 Gerando o instalador" -ForegroundColor Cyan
# Esvaziada antes: sobrando um .exe de um build anterior, uma falha silenciosa aqui
# seria coroada copiando o instalador velho como se fosse o novo.
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Force -Path $staging | Out-Null

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
if ($installer.Name -notlike "*$alvo*") {
    throw "O instalador saiu como '$($installer.Name)', que nao corresponde a versao $alvo."
}

New-Item -ItemType Directory -Force -Path $release | Out-Null
Copy-Item $installer.FullName $release -Force

Write-Host ""
Write-Host "Instalador gerado: $(Join-Path $release $installer.Name)" -ForegroundColor Green
Write-Host "Versao $alvo. Confira depois de instalar com:" -ForegroundColor Green
Write-Host "  (Invoke-RestMethod http://127.0.0.1:8000/health).version"
