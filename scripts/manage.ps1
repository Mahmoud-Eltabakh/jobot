<#
.SYNOPSIS
    Jobot Development and Operations Management Automation Script (Windows PowerShell)
.DESCRIPTION
    Automates local environment setup, testing, Docker builds, Compose stack lifecycle, and backup operations.
#>

param(
    [Parameter(Position=0)]
    [ValidateSet("setup", "test", "dev", "docker-build", "docker-up", "docker-up-host-ollama", "docker-down", "k8s-deploy", "backup", "help")]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host @"
============================================================
              JOBOT AUTOMATION CLI (PowerShell)
============================================================
Usage: .\scripts\manage.ps1 <command>

Available Commands:
  setup                  - Initialize virtual environment, install requirements and Playwright
  test                   - Run complete pytest test suite with coverage
  dev                    - Launch local FastAPI development server with hot reload
  docker-build           - Build production Docker image (jobot:latest)
  docker-up              - Build & start Docker Compose stack (Jobot + Ollama container)
  docker-up-host-ollama  - Build & start Jobot connected to Ollama running on your host machine
  docker-down            - Stop Docker Compose stack
  k8s-deploy             - Apply all Kubernetes manifests from k8s/ directory
  backup                 - Create a timestamped backup archive of data/ (SQLite + Chroma)
  help                   - Display this help message
============================================================
"@
}

switch ($Command) {
    "setup" {
        Write-Host "[+] Initializing Python virtual environment..." -ForegroundColor Cyan
        if (-not (Test-Path ".venv")) {
            python -m venv .venv
        }
        Write-Host "[+] Installing Python dependencies..." -ForegroundColor Cyan
        .\.venv\Scripts\pip install -r requirements.txt
        Write-Host "[+] Installing Playwright Chromium browser..." -ForegroundColor Cyan
        .\.venv\Scripts\playwright install chromium
        Write-Host "[✓] Jobot development setup complete!" -ForegroundColor Green
    }
    "test" {
        Write-Host "[+] Running test suite..." -ForegroundColor Cyan
        .\.venv\Scripts\pytest.exe -v
    }
    "dev" {
        Write-Host "[+] Launching Jobot development server on http://localhost:8000..." -ForegroundColor Cyan
        .\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
    }
    "docker-build" {
        Write-Host "[+] Building production Docker image jobot:latest..." -ForegroundColor Cyan
        docker build -t jobot:latest .
        Write-Host "[+] Cleaning up untagged dangling images..." -ForegroundColor Cyan
        docker image prune -f --filter "dangling=true" | Out-Null
        Write-Host "[✓] Docker build successful!" -ForegroundColor Green
    }
    "docker-up" {
        Write-Host "[+] Building & starting Docker Compose stack in detached mode..." -ForegroundColor Cyan
        docker compose -f docker-compose.yml up --build -d
        docker image prune -f --filter "dangling=true" | Out-Null
        Write-Host "[✓] Jobot stack running! Access web dashboard at http://localhost:8000" -ForegroundColor Green
    }
    "docker-up-host-ollama" {
        Write-Host "[+] Building & starting Jobot connected to Host Ollama (http://host.docker.internal:11434)..." -ForegroundColor Cyan
        docker compose -f docker-compose.host-ollama.yml up --build -d
        docker image prune -f --filter "dangling=true" | Out-Null
        Write-Host "[✓] Jobot running with Host Ollama! Access web dashboard at http://localhost:8000" -ForegroundColor Green
    }
    "docker-down" {
        Write-Host "[+] Stopping Docker Compose stack..." -ForegroundColor Cyan
        docker compose down
    }
    "k8s-deploy" {
        Write-Host "[+] Deploying Jobot to Kubernetes cluster..." -ForegroundColor Cyan
        kubectl apply -f k8s/jobot-all.yaml
        Write-Host "[✓] Kubernetes manifests applied!" -ForegroundColor Green
    }
    "backup" {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupDir = "backups"
        if (-not (Test-Path $backupDir)) {
            New-Item -ItemType Directory -Path $backupDir | Out-Null
        }
        $destZip = "$backupDir\jobot_backup_$timestamp.zip"
        Write-Host "[+] Creating backup archive: $destZip..." -ForegroundColor Cyan
        Compress-Archive -Path "data\*" -DestinationPath $destZip -Force
        Write-Host "[✓] Backup created successfully!" -ForegroundColor Green
    }
    Default {
        Show-Help
    }
}
