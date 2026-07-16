@echo off
cd /d "%~dp0"

if not exist ".env" (
    echo FRONTEND_HMR=true > .env
    echo FRONTEND_HOSTNAME=http://localhost:8010 >> .env
    echo DJANGO_HOSTNAME=http://localhost:8080 >> .env
)

set DJANGO_DB=sqlite
set LOG_DIR=tmp
set DEBUG=true
set LOG_LEVEL=DEBUG
set DJANGO_SETTINGS_MODULE=core.settings.label_studio

echo Starting Label Studio Backend...
echo Access: http://localhost:8080
echo Press Ctrl+C to stop.
echo.

poetry run python label_studio\manage.py runserver --noreload
