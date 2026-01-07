#!/bin/bash

# Theology AI Lab - 실행 스크립트 (Mac)
# ===========================================

cd "$(dirname "$0")"

echo "🚀 Theology AI Lab을 실행합니다..."

# 1. 가상환경 확인
if [ ! -f "03_System/venv/bin/activate" ]; then
    echo "❌ 가상환경이 설치되어 있지 않습니다."
    echo "👉 우선 '1_INSTALL_MAC.command'를 실행하여 설치를 완료해주세요."
    read -p "엔터를 누르면 종료합니다..."
    exit 1
fi

# 2. .env 확인
if [ ! -f ".env" ]; then
    echo "⚙️  기본 환경 설정 파일을 생성합니다..."
    cat > .env << EOL
DATA_ROOT=.
CHROMA_DB_DIR=./02_Brain/vector_db
ARCHIVE_DIR=./01_Library/archive
INBOX_DIR=./01_Library/inbox
APP_TITLE=Kerygma Th Library
EOL
fi

# 3. 앱 실행
echo "🌐 브라우저에서 연구소가 열립니다..."
source 03_System/venv/bin/activate
cd 03_System
streamlit run app.py
