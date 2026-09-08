# 3D Cadastral Intelligence - PowerShell One-Click Launcher
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   3D Cadastral Intelligence & Property Identification System" -ForegroundColor Green
Write-Host "                  One-Click Launcher (PowerShell)" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n[*] Ensuring demo database is populated..." -ForegroundColor Yellow
& "$Root\src\backend\.venv\Scripts\python.exe" -m app.seeds.seed_demo_data --db-url sqlite:///./cadastral_dev.db

Write-Host "`n[*] Launching Backend API on http://127.0.0.1:8000 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\src\backend'; & '.\.venv\Scripts\Activate.ps1'; uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "`n[*] Launching Frontend Portal on http://127.0.0.1:5173 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\src\frontend'; npm run dev -- --host 127.0.0.1 --port 5173"

Write-Host "`n======================================================================" -ForegroundColor Cyan
Write-Host " Opening browser at http://localhost:5173 ..." -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
