@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "ls_tools\launcher.py" --repair-taskbar-shortcut
) else (
  python "ls_tools\launcher.py" --repair-taskbar-shortcut
)
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (
  echo Taskbar repair PASS.
) else (
  echo Taskbar repair FAIL.
)
pause
exit /b %RC%
