@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RECOVER_TO_V228_KNOWN_GOOD.ps1"
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (
  echo Recovery PASS - LS v2.28 darbojas.
) else (
  echo Recovery FAIL - atsuti RECOVER_V228.log.
)
pause
exit /b %RC%
