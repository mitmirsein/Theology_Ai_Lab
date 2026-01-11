#!/bin/bash

# Theology AI Lab - Smart Launcher (Mac)
# ======================================

cd "$(dirname "$0")"

echo "🚀 Theology AI Lab 실행 요청..."

# 0. Check Virtual Env
if [ ! -f "03_System/venv/bin/activate" ]; then
    echo "❌ 설치가 필요합니다. '1_INSTALL_MAC.command'를 먼저 실행하세요."
    read -p "엔터를 누르면 종료합니다..."
    exit 1
fi

# 1. Check if Streamlit is already running
# lsof -i :8501 로 포트 점유 확인
if lsof -i :8501 > /dev/null; then
    echo ""
    echo "⚡️ 이미 연구소가 실행 중입니다!"
    echo "   (새로 서버를 켜지 않고 브라우저만 엽니다)"
    echo ""
    open "http://localhost:8501"
    
    # 잠깐 보여주고 종료 (기존 터미널은 살아있을 테니)
    sleep 2
    exit 0
fi

# 2. Check .env
if [ ! -f ".env" ]; then
    # (이전과 동일한 .env 생성 로직)
    echo "⚙️  초기 설정(.env) 생성 중..."
    cat > .env << EOL
# [Google Drive Cloud Paths]
INBOX_DIR=./01_Library/inbox
ARCHIVE_DIR=./01_Library/archive
DB_PATH=./02_Brain/vector_db

# [Setting]
APP_TITLE=Theology AI Lab (Cloud)
EOL
fi

# 3. Launch App
echo ""
echo "✅ 서버를 시작합니다. (잠시 후 브라우저가 열립니다)"
echo "--------------------------------------------------------"
echo "💡 안내:"
echo "   - 이 검은 창(터미널)은 서버입니다. 켜두세요. (최소화 OK)"
echo "   - 끄려면 키보드에서 [Ctrl + C]를 누르세요."
echo "   - 다시 접속하려면 이 파일을 다시 실행하거나,"
echo "     브라우저 주소창에 localhost:8501 을 입력하세요."
echo "--------------------------------------------------------"

source 03_System/venv/bin/activate
cd 03_System
streamlit run app.py
