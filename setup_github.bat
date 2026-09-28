@echo off
chcp 65001 >nul
REM ===== สำหรับผู้พัฒนา (เครื่องคุณ) — รันครั้งเดียวตอนเริ่ม =====
REM สร้าง repo บน GitHub + อัปโค้ดครั้งแรก + สร้าง zip ไว้ส่งแฟน
cd /d "%~dp0"
py tools\release.py setup
pause
