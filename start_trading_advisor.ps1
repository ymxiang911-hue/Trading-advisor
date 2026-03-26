param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appPath = Join-Path $projectRoot 'app.py'

if (-not (Test-Path $appPath)) {
    throw "app.py not found: $appPath"
}

$pythonExe = $null

try {
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
} catch {
    $fallbackPython = 'C:\Program Files\Python314\python.exe'
    if (Test-Path $fallbackPython) {
        $pythonExe = $fallbackPython
    }
}

if (-not $pythonExe) {
    throw 'Python was not found.'
}

$pythonDir = Split-Path -Parent $pythonExe
$pythonwExe = Join-Path $pythonDir 'pythonw.exe'

if (Test-Path $pythonwExe) {
    $launchExe = $pythonwExe
} else {
    $launchExe = $pythonExe
}

$checkCommand = "import importlib.util; print(importlib.util.find_spec('efinance') is not None)"
$hasEfinance = & $pythonExe -c $checkCommand

if ($hasEfinance.Trim() -ne 'True') {
    throw 'efinance is missing. Run: pip install -r requirements.txt'
}

if ($CheckOnly) {
    Write-Host 'Environment check passed.'
    Write-Host "Project: $projectRoot"
    Write-Host "Python: $pythonExe"
    Write-Host "Launcher: $launchExe"
    exit 0
}

Start-Process -FilePath $launchExe -ArgumentList "`"$appPath`"" -WorkingDirectory $projectRoot
