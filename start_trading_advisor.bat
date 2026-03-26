@echo off
setlocal

cd /d "%~dp0"

set "PYTHONW=%LocalAppData%\Programs\Python\Python314\pythonw.exe"
if not exist "%PYTHONW%" set "PYTHONW=C:\Program Files\Python314\pythonw.exe"

if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%~dp0app.py"
) else (
    python "%~dp0app.py"
)
