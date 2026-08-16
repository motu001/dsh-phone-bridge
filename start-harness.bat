@echo off
rem ============================================================
rem  start-harness.bat - one-click launcher (background bridges)
rem  Bridges run in the background (no console windows) via
rem  pythonw; DeepSeek Harness web GUI opens in the foreground.
rem  ASCII-only file - never shows mojibake.
rem  Chinese notes are in usage-zh.txt
rem ============================================================
setlocal

set "DSH_BIN=C:\Users\Administrator\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\.bin\dsh.cmd"
set "PY314W=C:\Python314\pythonw.exe"
set "PY313W=C:\Users\Administrator\AppData\Local\Programs\Python\Python313\pythonw.exe"
set "BRIDGE_DIR=E:\comyui\phone_bridge"
set "CFD=C:\Program Files (x86)\cloudflared\cloudflared.exe"

if not exist "%DSH_BIN%"  echo [warn] dsh.cmd not found
if not exist "%PY314W%"   echo [warn] pythonw (3.14) not found
if not exist "%PY313W%"   echo [warn] pythonw (3.13) not found
if not exist "%CFD%"      echo [warn] cloudflared not found (media send off)
if not exist "%BRIDGE_DIR%\config.json" echo [warn] config.json missing

echo [1/3] start Telegram bridge (background) ...
start "" /b "%PY314W%" "%BRIDGE_DIR%\telegram_bridge.py" --config "%BRIDGE_DIR%\config.json"

echo [2/3] start QQ bridge (background, Python3.13) ...
start "" /b "%PY313W%" "%BRIDGE_DIR%\qq_bridge.py" --config "%BRIDGE_DIR%\config.json"

echo [3/3] start media tunnel (background, cloudflared) ...
start "" /b "%PY314W%" "%BRIDGE_DIR%\media_server.py" --config "%BRIDGE_DIR%\config.json"

echo start DeepSeek Harness web GUI (http://127.0.0.1:3080) ...
call "%DSH_BIN%" web

echo.
echo Harness exited. Bridges keep running in background. stop: stop-harness.bat
pause
endlocal