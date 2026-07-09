# Schooldom + Phoenix AI — Start All Servers
# Run this from the virtual-school-platform folder:
#   powershell -ExecutionPolicy Bypass -File .\start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $backend "frontend"
$venv = Join-Path $backend "venv\Scripts\python.exe"
$ollamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"

Write-Host ""
Write-Host "  Schooldom Launcher" -ForegroundColor Cyan
Write-Host "  ==================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Ollama ──────────────────────────────────────────────────────────────────
Write-Host "[1/3] Checking Ollama (Phoenix AI backend)..." -ForegroundColor Yellow
try {
    $ollamaStatus = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    Write-Host "      Ollama is already running. Good." -ForegroundColor Green
} catch {
    if (Test-Path $ollamaExe) {
        Write-Host "      Starting Ollama..." -ForegroundColor Yellow
        Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 3
        Write-Host "      Ollama started." -ForegroundColor Green
    } else {
        Write-Host "      WARNING: Ollama not found at $ollamaExe" -ForegroundColor Red
        Write-Host "      Download from https://ollama.com and run: ollama pull llama3.2:3b" -ForegroundColor Red
    }
}

# ── 2. Django ─────────────────────────────────────────────────────────────────
Write-Host "[2/3] Starting Django API server (port 8000)..." -ForegroundColor Yellow
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$backend'; & '$venv' manage.py runserver" `
    -WindowStyle Normal

# ── 3. Vite ───────────────────────────────────────────────────────────────────
Write-Host "[3/3] Starting Vite frontend (port 5173)..." -ForegroundColor Yellow
$nodeExe = (Get-Command node -ErrorAction SilentlyContinue)?.Source
if (-not $nodeExe) {
    Write-Host "      WARNING: node not found on PATH." -ForegroundColor Red
} else {
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", `
        "Set-Location '$frontend'; node '.\node_modules\vite\bin\vite.js'" `
        -WindowStyle Normal
}

Write-Host ""
Write-Host "  All servers launching in separate windows." -ForegroundColor Cyan
Write-Host "  Open http://localhost:5173 in your browser." -ForegroundColor Cyan
Write-Host ""
