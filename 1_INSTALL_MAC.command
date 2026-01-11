#!/bin/bash

# Theology AI Lab v4 - Cloud Edition Installer (Mac)
# ==========================================================

cd "$(dirname "$0")"

echo "☁️  Theology AI Lab (Cloud Edition) 설치를 시작합니다..."

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
if [ -d "03_System/venv" ]; then
    rm -rf 03_System/venv
fi
python3.11 -m venv 03_System/venv

if [ ! -f "03_System/venv/bin/activate" ]; then
    echo "❌ 가상환경 생성 실패! Python 설치 상태를 확인해주세요."
    exit 1
fi

# 3. Install Requirements (from pyproject.toml)
echo "⬇️  라이브러리 설치 중 (Viewer Mode)..."
source 03_System/venv/bin/activate
pip install --upgrade pip

# Install main dependencies (Lightweight Viewer)
# pyproject.toml이 03_System 안에 있으므로 해당 경로 사용
pip install -e ./03_System

echo "✅ 라이브러리 설치 완료."

# 4. Setup .env (Template)
if [ ! -f ".env" ]; then
    echo "⚙️  초기 설정 파일 생성 (.env)..."
    cat > .env << EOL
# [Google Drive Cloud Paths]
# 동기화를 위해 구글 드라이브 내의 절대 경로로 수정하는 것을 권장합니다.
# 예: /Users/yourname/Library/CloudStorage/GoogleDrive-email/...
INBOX_DIR=./01_Library/inbox
ARCHIVE_DIR=./01_Library/archive
DB_PATH=./02_Brain/vector_db

# [AI API Keys]
# ANTHROPIC_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=AIza...

# [Settings]
APP_TITLE=Theology AI Lab (Cloud)
EOL
    echo "ℹ️  기본 설정이 적용되었습니다. 추후 Google Drive 연동을 위해 .env 경로를 수정하세요."
else
    echo "ℹ️  기존 .env 설정을 유지합니다."
fi

# 5. Complete & Launch
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
