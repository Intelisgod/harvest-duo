@echo off
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [!] Python not found.
    pause
    exit /b 1
)

%PY% tools\furn_preview.py
pause
