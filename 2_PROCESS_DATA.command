#!/bin/bash
cd "$(dirname "$0")"

echo "🏭 데이터 공장을 가동합니다..."
echo "📂 Inbox: ./01_Library/inbox"
echo "📂 Archive: ./01_Library/archive"

source 03_System/venv/bin/activate

# 2. Run Builder
python3 03_System/utils/db_builder.py
read -p "엔터를 누르면 종료합니다..."
