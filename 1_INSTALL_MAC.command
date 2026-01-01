#!/bin/bash

# Theology AI Lab - One-Click Installer (Mac)
# ===========================================

cd "$(dirname "$0")"

echo "📦 Theology AI Lab 설치를 시작합니다..."

# 1. Check Python 3.11 (Robust Loop)
while ! command -v python3.11 &> /dev/null; do
    echo "❌ Python 3.11이 감지되지 않습니다."
    echo "👉 다운로드 페이지를 엽니다: https://www.python.org/ftp/python/3.11.9/python-3.11.9-macos11.pkg"
    open "https://www.python.org/ftp/python/3.11.9/python-3.11.9-macos11.pkg"
    echo "⚠️  설치를 완료한 후, 터미널을 껐다가 다시 실행해야 할 수도 있습니다."
    read -p "설치가 완료되었다면 엔터를 눌러주세요 (재확인합니다)..."
done

echo "✅ Python 3.11 감지됨."

# 2. Create Virtual Environment
echo "🛠️  가상환경(Virtual Environment) 생성 중..."
python3.11 -m venv 03_System/venv

if [ ! -f "03_System/venv/bin/activate" ]; then
    echo "❌ 가상환경 생성 실패! Python 설치 상태를 확인해주세요."
    exit 1
fi

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

# 5. Complete & Launch App
echo ""
echo "✅ =========================================="
echo "   설치가 완료되었습니다!"
echo "============================================"
echo ""
echo "🚀 연구소를 바로 실행합니다..."
echo "   (브라우저가 자동으로 열립니다)"
echo ""

# Launch the app directly
./3_START_MAC.command
