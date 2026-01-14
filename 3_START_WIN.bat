@echo off
chcp 65001 > nul
title Theology AI Lab - Launcher
cd /d "%~dp0"

echo 🚀 Theology AI Lab 실행 요청...

:: 0. Check Virtual Env
if not exist "03_System\venv\Scripts\activate.bat" (
    echo ❌ 설치가 필요합니다. '1_INSTALL_WIN.bat'을 먼저 실행하세요.
    pause
    exit /b
)

:: 1. Check if Streamlit is already running (Port 8501)
netstat -ano | findstr :8501 > nul
if %errorlevel%==0 (
    echo.
    echo ⚡️ 이미 연구소가 실행 중입니다!
    echo    ^(새로 서버를 켜지 않고 브라우저만 엽니다^)
    echo.
    start http://localhost:8501
    timeout /t 2 > nul
    exit /b
)

:: 2. Check .env
if not exist ".env" (
    echo ⚙️  초기 설정(.env) 생성 중...
    (
        echo # [Google Drive Cloud Paths]
        echo INBOX_DIR=./01_Library/inbox
        echo ARCHIVE_DIR=./01_Library/archive
        echo DB_PATH=./02_Brain/vector_db
        echo.
        echo # [Setting]
        echo APP_TITLE=Theology AI Lab ^(Cloud^)
    ) > .env
)

:: 3. Launch App
echo.
echo ✅ 서버를 시작합니다. (잠시 후 브라우저가 열립니다)
echo --------------------------------------------------------
echo 💡 안내:
echo    - 이 검은 창은 서버입니다. 켜두세요. (최소화 OK)
echo    - 끄려면 창을 닫거나 [Ctrl + C]를 누르세요.
echo    - 다시 접속하려면 이 파일을 다시 실행하면 됩니다.
echo --------------------------------------------------------

call 03_System\venv\Scripts\activate.bat
cd 03_System
streamlit run app.py
pause
