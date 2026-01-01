@echo off
chcp 65001 >nul
echo Запуск веб-інтерфейсу...
cd /d "%~dp0"
call venv\Scripts\activate.bat
python web_admin/app.py
pause

