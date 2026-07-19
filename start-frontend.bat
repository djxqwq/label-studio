@echo off
cd /d "%~dp0"
chcp 65001 >nul

set NODE_ENV=development

if not exist "web\node_modules" (
    echo [ERROR] web\node_modules not found
    echo Run: cd web ^&^& npm install --registry=https://registry.npmmirror.com --legacy-peer-deps
    pause
    exit /b 1
)

if not exist ".env" (
    echo FRONTEND_HMR=true>.env
    echo FRONTEND_HOSTNAME=http://localhost:8010>>.env
    echo DJANGO_HOSTNAME=http://localhost:8080>>.env
)

echo ============================================
echo   Label Studio Frontend (HMR)
echo   http://localhost:8010
echo   Backend: http://localhost:8080
echo   Ctrl+C to stop
echo ============================================
echo.

cd web
call npm run ls:dev
pause
