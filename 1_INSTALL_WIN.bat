@echo off
chcp 65001
cd /d "%~dp0"

echo 📦 Theology AI Lab 설치를 시작합니다...

:: 1. Check Python
python --version 2>NUL
if errorlevel 1 (
    echo ❌ Python이 설치되어 있지 않습니다.
    echo 👉 다운로드 페이지를 엽니다...
    start https://www.python.org/downloads/
    pause
    exit
)

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

:: 5. Launch
echo ✅ 설치 완료!
echo 🚀 연구소를 실행합니다...

where code >nul 2>nul
if %errorlevel% neq 0 (
    echo ⚠️ Antigravity/VSCode가 없습니다.
    start https://code.visualstudio.com
    pause
)

start .
pause
