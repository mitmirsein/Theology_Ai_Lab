#!/bin/bash
cd "$(dirname "$0")"

echo "📡 Theology AI Server를 시작합니다..."
echo "🔗 Antigravity와 연결 대기 중..."

source 03_System/venv/bin/activate

# 2. Run Server
python3 03_System/server.py
read -p "엔터를 누르면 종료합니다..."
