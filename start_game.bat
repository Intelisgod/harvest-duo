@echo off
title Harvest Duo - Launcher
cd /d "%~dp0"

echo ============================================
echo            HARVEST DUO  - Launcher
echo   Two-player co-op farm (Stardew-style)
echo ============================================
echo.

REM --- find Python ---
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [!] Python was not found on this computer.
    echo     Please install Python 3 from https://www.python.org/downloads/
    echo     During install, tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo Using Python command: %PY%
echo.

REM --- make sure pygame is installed ---
%PY% -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo Installing pygame ^(first run only^)...
    %PY% -m pip install --upgrade pip >nul 2>nul
    %PY% -m pip install pygame
    if errorlevel 1 (
        echo.
        echo [!] Failed to install pygame. Check your internet connection.
        pause
        exit /b 1
    )
)

echo.
echo Starting the game... have fun!  (close this window to quit)
echo.
%PY% main.py

if errorlevel 1 (
    echo.
    echo [!] The game exited with an error. Screenshot the message above if you need help.
    pause
)
