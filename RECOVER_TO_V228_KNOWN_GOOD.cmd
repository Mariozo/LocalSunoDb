@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RECOVER_TO_V228_KNOWN_GOOD.ps1"
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (
  echo Recovery PASS - LS v2.28 is running.
) else (
  echo Recovery FAIL - send RECOVER_V228.log.
)
pause
exit /b %RC%
