@echo off
cd /d "%~dp0"
chcp 65001 >nul

set "PATH=C:\Users\Administrator\.conda\envs\sop;%PATH%"

set BASE_DATA_DIR=%~dp0data
set PYTHONPATH=%~dp0
set DJANGO_DB=sqlite
set LOG_DIR=tmp
set DEBUG=true
set LOG_LEVEL=DEBUG
set DJANGO_SETTINGS_MODULE=core.settings.label_studio
set CSRF_TRUSTED_ORIGINS=http://localhost:8010,http://localhost:8080

if not exist "%BASE_DATA_DIR%" mkdir "%BASE_DATA_DIR%"

echo ============================================
echo   Label Studio Backend
echo   http://localhost:8080
echo   DB: %BASE_DATA_DIR%\label_studio.sqlite3
echo   Ctrl+C to stop
echo ============================================
echo.

python label_studio\manage.py runserver
pause
