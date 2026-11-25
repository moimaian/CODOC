<#
.SYNOPSIS
  CODOC - instalador para Windows 10/11 (PowerShell). / CODOC installer for Windows 10/11.

.DESCRIPTION
  Instala o CODOC sem que o usuario precise abrir um terminal ou digitar comandos:

    1. copia o programa para %USERPROFILE%\CODOC (ou baixa do GitHub, se o script estiver sozinho);
    2. procura o Python 3.10 ou mais novo; se nao achar, baixa o Python 3.10.11 do python.org, confere a
       assinatura digital e instala so para o usuario atual (sem administrador);
    3. roda "python CODOC.py --setup", que cria o ambiente virtual (%USERPROFILE%\.venv\CODOC, Python 3.10.11),
       instala o runtime Visual C++ do Qt5 (o Windows pede a confirmacao de administrador uma vez), os pacotes
       essenciais e o AutoDock Vina 1.2.5 para Windows, e cria os atalhos CODOC na Area de Trabalho e no
       Menu Iniciar;
    4. abre o CODOC; na primeira vez ele mostra a janela Install Requirements para instalar o restante
       (RDKit, Meeko, PDB2PQR, Open Babel, Java, P2Rank, Vina-GPU...).

  Depois, use o atalho CODOC. Para rodar com duplo clique, use o CODOC_Windows.bat (que chama este script).

.PARAMETER InstallDir
  Pasta de instalacao. Padrao: %USERPROFILE%\CODOC (o CODOC procura o ambiente e as ferramentas a partir dela).

.PARAMETER SourceUrl
  Zip do GitHub usado quando este script roda fora da pasta do programa.

.PARAMETER NoLaunch
  Nao abre o CODOC no fim.

.PARAMETER NoRequirementsWindow
  Nao abre a janela Install Requirements na primeira vez.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\Install-CODOC.ps1
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:USERPROFILE 'CODOC'),
    [string]$SourceUrl = 'https://github.com/moimaian/CODOC/archive/refs/heads/main.zip',
    [switch]$NoLaunch,
    [switch]$NoRequirementsWindow
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

$PyVersion = '3.10.11'
$PyUrl = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-amd64.exe"
$UserFolders = @('PROJECTS', 'BASE', 'TEST', 'BENCHMARK')     # trabalho do usuario: nunca sobrescrito

function Write-Step([string]$Text) { Write-Host ''; Write-Host "[CODOC] $Text" -ForegroundColor Cyan }
function Write-Info([string]$Text) { Write-Host "[CODOC] $Text" }

function Find-Python {
    # Um Python 3.10 ou mais novo que funcione (py launcher, pasta padrao do instalador, PATH).
    $candidates = @()
    try {
        $fromLauncher = & py -3.10 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $fromLauncher) { $candidates += $fromLauncher.Trim() }
    } catch { }
    $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe')
    try {
        # "python" do PATH: ignora o atalho falso da Microsoft Store e versoes antigas
        $fromPath = & python -c "import sys; print(sys.executable if sys.version_info[:2] >= (3, 10) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $fromPath) { $candidates += $fromPath.Trim() }
    } catch { }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    return $null
}

function Install-Python {
    $installer = Join-Path $env:TEMP "python-$PyVersion-amd64.exe"
    Write-Info "Baixando $PyUrl"
    Invoke-WebRequest -UseBasicParsing -Uri $PyUrl -OutFile $installer
    # So executa o instalador se a assinatura digital for valida e da Python Software Foundation.
    $signature = Get-AuthenticodeSignature -FilePath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notlike '*Python Software Foundation*') {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
        throw 'A assinatura digital do instalador do Python nao confere. Instalacao cancelada.'
    }
    Write-Info 'Instalando o Python (so para o seu usuario; pode levar alguns minutos)...'
    $process = Start-Process -FilePath $installer -Wait -PassThru -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=0', 'Include_test=0', 'Include_pip=1'
    Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    if ($process.ExitCode -ne 0) { throw "O instalador do Python terminou com o codigo $($process.ExitCode)." }
}

function Get-SourceFolder {
    # A pasta com o CODOC.py: a deste script ou, sem ela, o zip baixado do GitHub.
    $scriptFolder = $PSScriptRoot
    if (-not $scriptFolder) { $scriptFolder = (Get-Location).Path }
    if (Test-Path -LiteralPath (Join-Path $scriptFolder 'CODOC.py')) { return $scriptFolder }
    $temp = Join-Path $env:TEMP 'codoc-install'
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
    New-Item -ItemType Directory -Path $temp | Out-Null
    $zip = Join-Path $temp 'CODOC.zip'
    Write-Info "Baixando o CODOC de $SourceUrl"
    Invoke-WebRequest -UseBasicParsing -Uri $SourceUrl -OutFile $zip
    Expand-Archive -LiteralPath $zip -DestinationPath $temp -Force
    $found = Get-ChildItem -LiteralPath $temp -Recurse -Filter 'CODOC.py' | Select-Object -First 1
    if (-not $found) { throw 'O CODOC.py nao foi encontrado no zip baixado.' }
    return $found.DirectoryName
}

function Copy-Program([string]$Source, [string]$Destination) {
    if ((Resolve-Path -LiteralPath $Source).Path.TrimEnd('\') -ieq $Destination.TrimEnd('\')) {
        Write-Info "O programa ja esta em $Destination."
        return
    }
    Write-Info "Copiando o programa para $Destination"
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    # Nunca sobrescreve o trabalho do usuario que ja existe no destino (projetos, arquivos de BASE).
    $skip = @('.git', '__pycache__')
    foreach ($folder in $UserFolders) {
        if (Test-Path -LiteralPath (Join-Path $Destination $folder)) { $skip += $folder }
    }
    $arguments = @($Source, $Destination, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/XF', '*.pyc', '/XD') + $skip
    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Nao foi possivel copiar o programa (robocopy, codigo $LASTEXITCODE)." }
    $global:LASTEXITCODE = 0
}

function New-Shortcut([string]$Path, [string]$Target, [string]$Arguments, [string]$WorkDir, [string]$Icon) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Path)
    $link.TargetPath = $Target
    $link.Arguments = $Arguments
    $link.WorkingDirectory = $WorkDir
    $link.Description = 'CODOC - Computational Molecular Docking Platform'
    if (Test-Path -LiteralPath $Icon) { $link.IconLocation = $Icon }
    $link.Save()
}

try {
    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Cyan
    Write-Host '  CODOC - instalacao para Windows' -ForegroundColor Cyan
    Write-Host '============================================================' -ForegroundColor Cyan

    if ($env:OS -ne 'Windows_NT') { throw 'Este instalador e para Windows. No Linux use: python3 CODOC.py ou o pacote .deb.' }
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'O CODOC exige o Windows de 64 bits.' }

    Write-Step '1/4  Programa'
    $source = Get-SourceFolder
    Copy-Program -Source $source -Destination $InstallDir
    $codoc = Join-Path $InstallDir 'CODOC.py'
    if (-not (Test-Path -LiteralPath $codoc)) { throw "CODOC.py nao encontrado em $InstallDir." }

    Write-Step '2/4  Python'
    $python = Find-Python
    if (-not $python) {
        Write-Info "Python 3.10 nao encontrado neste computador. Instalando o Python $PyVersion..."
        Install-Python
        $python = Find-Python
        if (-not $python) { throw "Nao foi possivel instalar o Python $PyVersion automaticamente. Instale-o por $PyUrl e rode este script de novo." }
    }
    Write-Info "Usando o Python: $python"

    Write-Step '3/4  Ambiente do CODOC (primeira vez: leva alguns minutos)'
    $env:CODOC_ASSUME_YES = '1'                    # responde "S" as confirmacoes do bootstrap
    $env:PYTHONUTF8 = '1'
    & $python $codoc --setup
    if ($LASTEXITCODE -ne 0) { throw "A preparacao do ambiente falhou (codigo $LASTEXITCODE). Leia as mensagens acima." }

    Write-Step '4/4  Atalhos'
    $venvPythonw = Join-Path $env:USERPROFILE '.venv\CODOC\Scripts\pythonw.exe'
    $icon = Join-Path $InstallDir 'ICONS\CODOC.ico'
    if (-not (Test-Path -LiteralPath $venvPythonw)) { throw "O ambiente nao foi criado ($venvPythonw nao existe)." }
    $shortcutArguments = '-X utf8 "' + $codoc + '"'
    $desktop = [Environment]::GetFolderPath('Desktop')
    $programs = [Environment]::GetFolderPath('Programs')
    foreach ($folder in @($desktop, $programs)) {
        $link = Join-Path $folder 'CODOC.lnk'
        if (-not (Test-Path -LiteralPath $link)) {
            New-Shortcut -Path $link -Target $venvPythonw -Arguments $shortcutArguments -WorkDir $InstallDir -Icon $icon
        }
        Write-Info "Atalho: $link"
    }

    Write-Host ''
    Write-Host '[CODOC] Instalacao concluida.' -ForegroundColor Green
    Write-Host '[CODOC] Da proxima vez, abra o CODOC pelo atalho da Area de Trabalho ou do Menu Iniciar.'
    if (-not $NoLaunch) {
        Write-Info 'Abrindo o CODOC...'
        if (-not $NoRequirementsWindow) { $env:CODOC_OPEN_REQUIREMENTS = '1' }
        Start-Process -FilePath $venvPythonw -ArgumentList $shortcutArguments -WorkingDirectory $InstallDir
    }
    exit 0
}
catch {
    Write-Host ''
    Write-Host "[CODOC] ERRO: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
