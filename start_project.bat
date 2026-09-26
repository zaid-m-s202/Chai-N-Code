@echo off
title 3D Cadastral Intelligence Launcher
echo ======================================================================
echo    3D Cadastral Intelligence ^& Property Identification System
echo                   One-Click Launcher (No Docker Required)
echo ======================================================================
echo.

cd /d "%~dp0"

echo [*] Initializing demo database with pilot wards (Pune ^& Bengaluru)...
REM call "%~dp0src\backend\.venv\Scripts\python.exe" -m app.seeds.seed_demo_data --db-url sqlite:///%~dp0cadastral_dev.db

echo.
echo [*] Launching Backend API Server on http://127.0.0.1:8000 ...
start "3D Cadastre Backend API" cmd /k "cd /d "%~dp0src\backend" && .venv\Scripts\activate && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo.
echo [*] Launching Frontend Web Portal on http://127.0.0.1:5173 ...
start "3D Cadastre Frontend Portal" cmd /k "cd /d "%~dp0src\frontend" && npm run dev -- --host 127.0.0.1 --port 5173"

echo.
echo ======================================================================
echo  All services launched successfully!
echo  Opening the government portal in your browser: http://localhost:5173
echo ======================================================================
timeout /t 3 >nul
start http://localhost:5173