@echo off
cd /d "%~dp0"

if not exist ".env" (
    echo FRONTEND_HMR=true > .env
    echo FRONTEND_HOSTNAME=http://localhost:8010 >> .env
    echo DJANGO_HOSTNAME=http://localhost:8080 >> .env
)

set NODE_ENV=development

echo Starting Label Studio Frontend...
echo Access: http://localhost:8010
echo Backend: http://localhost:8080
echo Press Ctrl+C to stop.
echo.

cd web
echo n | npm run ls:dev
