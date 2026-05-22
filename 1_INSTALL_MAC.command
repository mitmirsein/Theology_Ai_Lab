#!/bin/bash

# Theology AI Lab - Local Edition Installer (Mac)
# ==========================================================

cd "$(dirname "$0")"

echo "💻 Theology AI Lab (Local Edition) 설치를 시작합니다..."

# 1. Check uv (The Modern Way)
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv (High-speed installer)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "✅ uv ready."

# 2. Create Virtual Environment with uv
echo "🛠️  가상환경(Virtual Environment) 생성 중 (via uv)..."
# uv handles python version automatically
uv venv 03_System/venv --python 3.11

if [ ! -f "03_System/venv/bin/activate" ]; then
    echo "❌ 가상환경 생성 실패!"
    exit 1
fi

# 3. Install Requirements (via uv pip)
echo "⬇️  라이브러리 설치 중 (Ultra-fast Mode)..."
source 03_System/venv/bin/activate

# uv pip sync is cleaner, but install works for setup.py
uv pip install -e ./03_System
echo "✅ 라이브러리 설치 완료."

# 4. Create local library folders
mkdir -p 01_Library/inbox 01_Library/archive 02_Brain/vector_db

# 5. Setup .env (Template)
if [ ! -f ".env" ]; then
    echo "⚙️  초기 설정 파일 생성 (.env)..."
    cat > .env << EOL
# [Local Library Paths]
INBOX_DIR=./01_Library/inbox
ARCHIVE_DIR=./01_Library/archive
DB_PATH=./02_Brain/vector_db

# [AI API Keys]
# ANTHROPIC_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=AIza...

# [Settings]
APP_TITLE=Theology AI Lab (Local)
EOL
    echo "ℹ️  기본 로컬 설정이 적용되었습니다."
else
    echo "ℹ️  기존 .env 설정을 유지합니다."
fi

# 6. Complete & Launch
echo ""
echo "✅ =========================================="
echo "   설치가 완료되었습니다!"
echo "============================================"
echo ""
echo "🚀 연구소를 실행합니다..."
echo "   잠시 후 브라우저가 열리면 http://localhost:8501 주소를 확인하세요."
echo ""

# Launch the app
./3_START_MAC.command
