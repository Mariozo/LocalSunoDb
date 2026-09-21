@echo off
setlocal
set "ROOT=%~dp0"
set "PYW=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw.exe"
start "" /wait "%PYW%" "%ROOT%ls_tools\launcher.py" --restart-backend
exit /b %ERRORLEVEL%
