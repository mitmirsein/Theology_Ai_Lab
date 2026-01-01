@echo off
chcp 65001
cd /d "%~dp0"

echo 📦 Theology AI Lab 설치를 시작합니다...

:: 1. Check Python
:CHECK_PYTHON
python --version 2>NUL
if errorlevel 1 (
    echo ❌ Python이 설치되어 있지 않습니다.
    echo 👉 다운로드 페이지를 엽니다: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    start https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo ⚠️ 설치 후 터미널을 다시 실행해야 할 수 있습니다.
    echo 설치가 완료되었다면 엔터를 눌러주세요...
    pause >nul
    goto CHECK_PYTHON
)
echo ✅ Python 감지됨.

:: 2. Create Venv
echo 🛠️ 가상환경 생성 중...
python -m venv 03_System\venv

:: 3. Install Requirements
echo ⬇️ AI 라이브러리 설치 중...
call 03_System\venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r 03_System\requirements.txt

:: 4. Setup .env
echo ⚙️ 환경 설정 중...
(
echo DATA_ROOT=.
echo CHROMA_DB_DIR=./02_Brain/vector_db
echo ARCHIVE_DIR=./01_Library/archive
echo INBOX_DIR=./01_Library/inbox
) > .env

:: 5. Complete & Launch App
echo.
echo ✅ ==========================================
echo    설치가 완료되었습니다!
echo ============================================
echo.
echo 🚀 연구소를 바로 실행합니다...
echo    (브라우저가 자동으로 열립니다)
echo.

:: Launch the app directly
call 3_START_WIN.bat
