@echo off
chcp 65001 > nul
setlocal

echo ==========================================================
echo ☁️  Theology AI Lab v4 - Cloud Edition Installer (Windows)
echo ==========================================================
echo.

cd /d "%~dp0"

:: 1. Check Python 3.11
python --version 2>NUL
if errorlevel 1 goto :NoPython
python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>NUL
if errorlevel 1 goto :OldPython

echo ✅ Python 3.11+ 감지됨.
goto :CreateVenv

:NoPython
echo ❌ Python이 설치되어 있지 않습니다.
echo 👉 https://www.python.org/downloads/ 에서 Python 3.11 이상을 설치해주세요.
echo    (설치 시 'Add Python to PATH' 옵션을 꼭 체크하세요!)
pause
exit /b

:OldPython
echo ❌ Python 버전이 너무 낮습니다. (3.11 이상 필요)
echo 👉 https://www.python.org/downloads/ 에서 최신 버전을 설치해주세요.
pause
exit /b

:CreateVenv
echo.
echo 🛠️  가상환경(venv) 생성 중...
if exist "03_System\venv" rmdir /s /q "03_System\venv"
python -m venv 03_System\venv

if not exist "03_System\venv\Scripts\activate.bat" (
    echo ❌ 가상환경 생성 실패!
    pause
    exit /b
)

:: 3. Install Requirements
echo.
echo ⬇️  라이브러리 설치 중... (화면이 멈춘 것처럼 보일 수 있습니다)
call 03_System\venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e ./03_System

echo ✅ 라이브러리 설치 완료.

:: 4. Setup .env
if not exist ".env" (
    echo.
    echo ⚙️  초기 설정 파일 생성 (.env)...
    (
        echo # [Google Drive Cloud Paths]
        echo # 윈도우 구글 드라이브 경로는 보통 G:\My Drive\... 형식이거나
        echo # C:\Users\User\Google Drive\... 형식입니다.
        echo INBOX_DIR=./01_Library/inbox
        echo ARCHIVE_DIR=./01_Library/archive
        echo DB_PATH=./02_Brain/vector_db
        echo.
        echo # [AI API Keys]
        echo # ANTHROPIC_API_KEY=sk-...
        echo # OPENAI_API_KEY=sk-...
        echo # GOOGLE_API_KEY=AIza...
        echo.
        echo # [Settings]
        echo APP_TITLE=Theology AI Lab ^(Cloud^)
    ) > .env
    echo ℹ️  기본 설정이 적용되었습니다.
) else (
    echo ℹ️  기존 .env 설정을 유지합니다.
)

:: 5. Launch
echo.
echo ✅ ==========================================
echo    설치가 완료되었습니다!
echo ============================================
echo.
echo 🚀 연구소를 실행합니다...
echo.

call 3_START_WIN.bat
