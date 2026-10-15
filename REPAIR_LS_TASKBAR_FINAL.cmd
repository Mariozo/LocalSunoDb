@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "ls_tools\launcher.py" --repair-taskbar-shortcut
) else (
  python "ls_tools\launcher.py" --repair-taskbar-shortcut
)
exit /b %ERRORLEVEL%
