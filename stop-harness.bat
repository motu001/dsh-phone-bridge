@echo off
rem ============================================================
rem  stop-harness.bat - stop the phone bridges (Telegram/QQ/media)
rem  Does not close the DeepSeek Harness GUI.
rem  No pause: silently stops and exits (good for desktop shortcut).
rem ============================================================
setlocal
set "DIR=%~dp0"
echo stopping phone bridge processes ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%DIR%stop-bridges.ps1"
endlocal