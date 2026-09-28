@echo off
chcp 65001 >nul
title Harvest Duo
cd /d "%~dp0"

REM ---- find Python ----
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo.
    echo  [!] ไม่พบ Python ในเครื่องนี้
    echo      ติดตั้งจาก https://www.python.org/downloads/  ^(ตอนติดตั้งติ๊ก "Add Python to PATH"^)
    echo      จากนั้นเปิดไฟล์นี้อีกครั้ง
    start https://www.python.org/downloads/
    pause
    exit /b
)

echo  กำลังตรวจอัปเดต...
%PY% "%~dp0updater.py"

echo  เปิดเกม Harvest Duo...
%PY% "%~dp0launcher.py"
if errorlevel 1 (
    echo.
    echo  เกมปิดลงโดยมีข้อผิดพลาด - แคปหน้าจอนี้ส่งให้ผู้พัฒนาได้
    pause
)
