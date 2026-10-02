# FALCON - start everything for local development (Windows PowerShell).
#   Usage:  .\dev.ps1
# 1. starts Docker Desktop if needed   2. starts the database   3. applies migrations
# 4. opens the backend (:8010), the processing worker and the frontend (:5190) in their own windows

# Note: tools like docker and uv print progress on stderr, which Windows PowerShell 5.1 would
# treat as errors. So we check each program's exit code ($LASTEXITCODE) instead.
$root = $PSScriptRoot

function Test-Docker {
    cmd /c "docker info >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

function Assert-Success([string]$step) {
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $step" -ForegroundColor Red; exit 1 }
}

function Test-Port([int]$port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

function Start-Window([string]$title, [string]$folder, [string]$command) {
    $script = "`$Host.UI.RawUI.WindowTitle='$title'; Set-Location '$folder'; $command"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $script
}

if (-not (Test-Docker)) {
    Write-Host 'Starting Docker Desktop...'
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe",
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    )
    $exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $exe) { Write-Host 'Docker Desktop was not found. Install it, then run this script again.'; exit 1 }
    Start-Process $exe
    $deadline = (Get-Date).AddMinutes(4)
    while (-not (Test-Docker)) {
        if ((Get-Date) -gt $deadline) { Write-Host 'Docker did not start within 4 minutes.'; exit 1 }
        Start-Sleep -Seconds 3
    }
}

Write-Host 'Starting the database...'
Push-Location $root
cmd /c "docker compose up -d --wait 2>&1"
Assert-Success 'database start'
Pop-Location

Write-Host 'Applying database migrations...'
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
Push-Location $backend
cmd /c "uv run alembic upgrade head 2>&1"
Assert-Success 'database migrations'
Pop-Location

if (Test-Port 8010) { Write-Host 'Backend already running on :8010' }
else { Start-Window 'FALCON backend :8010' $backend 'uv run uvicorn app.main:app --reload --port 8010' }

$workerRunning = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*app.worker*' }
if ($workerRunning) { Write-Host 'Processing worker already running' }
else { Start-Window 'FALCON worker' $backend 'uv run python -m app.worker' }

if (Test-Port 5190) { Write-Host 'Frontend already running on :5190' }
else { Start-Window 'FALCON frontend :5190' $frontend 'npm run dev' }

Write-Host ''
Write-Host 'FALCON is starting:  http://localhost:5190   (API docs: http://localhost:8010/api/docs)'
