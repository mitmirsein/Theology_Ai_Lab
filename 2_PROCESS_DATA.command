#!/bin/bash
cd "$(dirname "$0")"

echo "🏭 데이터 공장을 가동합니다..."
echo "📂 Inbox: ./01_Library/inbox"
echo "📂 Archive: ./01_Library/archive"

source 03_System/venv/bin/activate

# 1. Process Inbox (PDF/TXT -> JSON)
python3 03_System/utils/local_pdf_processor.py 01_Library/inbox -o 01_Library/inbox

# 2. Build Vector Database (JSON -> ChromaDB) & Archive Files
python3 03_System/utils/db_builder.py

# 3. Update Lemma Index (Archive -> JSON Index)
python3 03_System/tools/build_lemma_index.py
read -p "엔터를 누르면 종료합니다..."
