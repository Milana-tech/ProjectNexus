$ErrorActionPreference = 'Stop'

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

if (-not (Test-Path .\.env)) {
  Copy-Item .\.env.example .\.env
  Write-Host 'Created .env from .env.example'
}

Write-Host 'Starting Project Nexus stack...'
docker compose up --build -d

Write-Host "`nServices:"
docker compose ps

Write-Host "`nURLs:"
Write-Host '- FastAPI:       http://localhost:8000/health'
Write-Host '- Frontend:      http://localhost:3000'
Write-Host '- PHP backend:   http://localhost:8001/health'

Write-Host "`nTip: to stop: docker compose down"
