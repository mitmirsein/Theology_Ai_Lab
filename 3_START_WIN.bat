@echo off
title Theology AI Lab - Start (Windows)

cd /d %~dp0

echo 🚀 Theology AI Lab을 실행합니다...

:: 1. 가상환경 확인
if not exist "03_System\venv\Scripts\activate.bat" (
    echo ❌ 가상환경이 설치되어 있지 않습니다.
    echo 👉 우선 '1_INSTALL_WIN.bat'을 실행하여 설치를 완료해주세요.
    pause
    exit /b
)

:: 2. .env 확인
if not exist ".env" (
    echo ⚙️  기본 환경 설정 파일을 생성합니다...
    (
    echo DATA_ROOT=.
    echo CHROMA_DB_DIR=./02_Brain/vector_db
    echo ARCHIVE_DIR=./01_Library/archive
    echo INBOX_DIR=./01_Library/inbox
    echo APP_TITLE=Kerygma Th Library
    ) > .env
)

:: 3. 앱 실행
echo 🌐 브라우저에서 연구소가 열립니다...
call 03_System\venv\Scripts\activate.bat
cd 03_System
streamlit run app.py
pause
