@echo off
rem ============================================================
rem  start-harness.bat - one-click launcher for DSH phone bridge
rem  v2: auto-installs DeepSeek Harness (dsh) if it is missing,
rem  finds Python/Node automatically, then starts all bridges.
rem  ASCII-only (never shows mojibake). See README for中文说明.
rem ============================================================
setlocal EnableExtensions
set "HERE=%~dp0"

rem ---------------- 0. find Python (for the bridges) ----------------
set "PYW="
where pythonw >nul 2>&1 && set "PYW=pythonw"
if not defined PYW (
  where python >nul 2>&1 && set "PYW=python"
)
if not defined PYW (
  echo [ERROR] Python not found. Install it from https://www.python.org/downloads
  echo         then re-run this script.
  pause
  exit /b 1
)

rem ---------------- 1. find Node.js / npm ----------------
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js not found. Install it from https://nodejs.org
  pause
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm not found with Node.js. Reinstall Node.js.
  pause
  exit /b 1
)

rem ---------- 2. auto-install DeepSeek Harness (dsh) if missing ----------
where dsh >nul 2>&1
if errorlevel 1 (
  echo.
  echo ==========================================================
  echo  DeepSeek Harness ^(dsh^) not found. Installing it now...
  echo  Running:  npm install -g @deepseek-ai/dsh
  echo  First run may take a few minutes. Please wait...
  echo ==========================================================
  call npm install -g @deepseek-ai/dsh
  if errorlevel 1 (
    echo [ERROR] dsh install failed. Check internet / npm registry.
    pause
    exit /b 1
  )
)
where dsh >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 'dsh' still not found in PATH. PATH may be stale.
  echo         Open a NEW terminal, run:    dsh --version
  echo         If it is still missing, run:  npm install -g @deepseek-ai/dsh
  pause
  exit /b 1
) else (
  set "DSH_RUN=dsh"
)

rem ---------------- 3. start the bridges ----------------
echo.
echo =========================================---
echo    DSH Phone Bridge
echo ============================================
echo [1/3] Starting Telegram bridge...
start "" /b "%PYW%" "%HERE%telegram_bridge.py" --config "%HERE%config.json"

echo [2/3] Starting QQ bridge...
start "" /b "%PYW%" "%HERE%qq_bridge.py" --config "%HERE%config.json"

echo [3/3] Starting media tunnel (cloudflared)...
set "CFD=C:\Program Files (x86)\cloudflared\cloudflared.exe"
if exist "%CFD%" (
  start "" /b "%PYW%" "%HERE%media_server.py" --config "%HERE%config.json"
) else (
  echo [skip] cloudflared not found - QQ file-send off ^(Telegram still works^).
)

rem ---------------- 4. launch DeepSeek Harness web UI ----------------
cd /d "%HERE%"
echo.
echo Opening DeepSeek Harness web UI at  http://127.0.0.1:3080
echo If a browser does not open automatically, visit that address.
call %DSH_RUN% web

echo.
echo Harness closed. Bridges keep running in background.
echo To stop bridges use stop-harness.bat
pause
endlocal
exit /b 0