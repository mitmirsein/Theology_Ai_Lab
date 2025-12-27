#!/bin/bash

# Theology AI Lab - One-Click Installer (Mac)
# ===========================================

cd "$(dirname "$0")"

echo "📦 Theology AI Lab 설치를 시작합니다..."

# 1. Check Python 3.11
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11이 감지되지 않습니다."
    echo "👉 다운로드 페이지를 엽니다: https://www.python.org/downloads/"
    open "https://www.python.org/downloads/"
    read -p "설치 후 엔터를 눌러주세요..."
fi

# 2. Create Virtual Environment
echo "🛠️  가상환경(Virtual Environment) 생성 중..."
python3.11 -m venv 03_System/venv

# 3. Install Requirements
echo "⬇️  AI 라이브러리 설치 중 (인터넷 속도에 따라 2~5분 소요)..."
source 03_System/venv/bin/activate
pip install --upgrade pip
pip install -r 03_System/requirements.txt

# 4. Setup .env
echo "⚙️  환경 설정 완료 (.env)..."
cat > .env << EOL
DATA_ROOT=.
CHROMA_DB_DIR=./02_Brain/vector_db
ARCHIVE_DIR=./01_Library/archive
INBOX_DIR=./01_Library/inbox
EOL

# 5. Check IDE & Launch
echo "✅ 설치 완료!"
echo "🚀 연구소를 실행합니다..."

if ! command -v code &> /dev/null; then
    echo "⚠️  Antigravity (또는 VS Code)가 없습니다."
    echo "👉 설치 페이지를 엽니다..."
    open "https://antigravity.ai"
    read -p "설치 후 엔터를 누르면 연구소가 열립니다..."
fi

# Launch Workspace
echo "📂 Theology_Lab 워크스페이스를 엽니다..."
# Try opening the workspace file (associates with Antigravity/VSCode)
open Theology_Lab.code-workspace || open .
read -p "엔터를 누르면 창을 닫습니다..."
