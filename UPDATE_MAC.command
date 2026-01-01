#!/bin/bash

# Kerygma Theology AI Lab - 업데이트 스크립트 (Mac)
# ================================================
# 데이터(vector_db, archive) 보존하면서 코드만 업데이트

cd "$(dirname "$0")"

echo ""
echo "🔄 =========================================="
echo "   Kerygma Theology AI Lab 업데이트"
echo "=========================================="
echo ""

# 1. 백업 확인
echo "📋 현재 상태 확인 중..."

if [ ! -d "01_Library" ] || [ ! -d "02_Brain" ]; then
    echo "❌ 기존 설치를 찾을 수 없습니다."
    echo "   신규 설치는 1_INSTALL_MAC.command를 사용하세요."
    read -p "엔터를 누르면 종료합니다..."
    exit 1
fi

echo "✅ 데이터 폴더 확인됨:"
echo "   - 01_Library/ (archive, inbox)"
echo "   - 02_Brain/ (vector_db)"

# 2. 새 버전 압축파일 확인
NEW_ZIP=$(ls -t Kerygma_*_Clean.zip 2>/dev/null | head -1)

if [ -z "$NEW_ZIP" ]; then
    echo ""
    echo "⚠️  새 버전 zip 파일이 없습니다."
    echo "   업데이트 zip 파일을 이 폴더에 넣어주세요."
    echo "   예: Kerygma_Theology_AI_Lab_v2.7.24_Clean.zip"
    read -p "엔터를 누르면 종료합니다..."
    exit 1
fi

echo ""
echo "📦 발견된 업데이트: $NEW_ZIP"
read -p "이 버전으로 업데이트하시겠습니까? [y/N] " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "업데이트가 취소되었습니다."
    exit 0
fi

# 3. 기존 코드 백업
echo ""
echo "💾 기존 코드 백업 중..."
BACKUP_DIR="03_System_backup_$(date +%Y%m%d_%H%M%S)"
mv 03_System "$BACKUP_DIR"
echo "   → $BACKUP_DIR"

# 4. 새 코드 추출
echo "📂 새 버전 코드 추출 중..."
unzip -q "$NEW_ZIP" "03_System/*" -d .

if [ ! -d "03_System" ]; then
    echo "❌ 추출 실패! 백업 복원 중..."
    mv "$BACKUP_DIR" 03_System
    exit 1
fi

# 5. 가상환경 재사용 (있으면)
if [ -d "$BACKUP_DIR/venv" ]; then
    echo "🐍 가상환경 재사용..."
    mv "$BACKUP_DIR/venv" 03_System/
fi

# 6. 의존성 업데이트
echo "⬇️  의존성 업데이트 중..."
source 03_System/venv/bin/activate 2>/dev/null || {
    echo "   가상환경 없음, 새로 생성..."
    python3.11 -m venv 03_System/venv
    source 03_System/venv/bin/activate
}
pip install --upgrade pip -q
pip install -r 03_System/requirements.txt -q

# 7. 완료
echo ""
echo "✅ =========================================="
echo "   업데이트 완료!"
echo "=========================================="
echo ""
echo "📊 보존된 데이터:"
echo "   - 01_Library/archive/ (청킹 데이터)"
echo "   - 02_Brain/vector_db/ (벡터 DB)"
echo "   - .env (API 키)"
echo ""
echo "💾 백업 위치: $BACKUP_DIR"
echo "   (문제 없으면 나중에 삭제해도 됩니다)"
echo ""

read -p "연구소를 실행하시겠습니까? [Y/n] " run
if [ "$run" != "n" ] && [ "$run" != "N" ]; then
    ./3_START_MAC.command
fi
