#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Theology AI Lab v2 - One-Click Installer (Mac)
# ═══════════════════════════════════════════════════════════════════
# 사용법: 이 파일을 더블클릭하세요
# ═══════════════════════════════════════════════════════════════════

cd "$(dirname "$0")"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🚀 Theology AI Lab v2 설치를 시작합니다..."
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ─────────────────────────────────────────────────────────────────
# 1. Docker Desktop 확인
# ─────────────────────────────────────────────────────────────────
echo "📦 Step 1/4: Docker Desktop 확인 중..."

if ! command -v docker &> /dev/null; then
    echo ""
    echo "❌ Docker Desktop이 설치되어 있지 않습니다."
    echo ""
    echo "👉 Docker Desktop 다운로드 페이지를 엽니다..."
    open "https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "⚠️  Docker Desktop을 설치한 후, 이 스크립트를 다시 실행하세요."
    echo ""
    read -p "엔터를 누르면 종료합니다..."
    exit 1
fi

echo "   ✅ Docker 명령어 확인됨"

# ─────────────────────────────────────────────────────────────────
# 2. Docker 실행 상태 확인
# ─────────────────────────────────────────────────────────────────
echo ""
echo "📦 Step 2/4: Docker 실행 상태 확인 중..."

if ! docker info &> /dev/null; then
    echo "   ⚠️  Docker가 실행 중이 아닙니다. 실행합니다..."
    open -a Docker

    echo "   ⏳ Docker 시작 대기 중..."
    attempt=0
    max_attempts=60  # 최대 2분 대기

    while ! docker info &> /dev/null; do
        sleep 2
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            echo ""
            echo "❌ Docker 시작 시간 초과. Docker Desktop을 수동으로 실행해주세요."
            read -p "엔터를 누르면 종료합니다..."
            exit 1
        fi
        printf "."
    done
    echo ""
fi

echo "   ✅ Docker 실행 중"

# ─────────────────────────────────────────────────────────────────
# 3. 환경 설정
# ─────────────────────────────────────────────────────────────────
echo ""
echo "📦 Step 3/4: 환경 설정 중..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "   ✅ .env 파일 생성 완료"
    else
        echo "   ⚠️  .env.example 파일이 없습니다. 기본 설정을 사용합니다."
    fi
else
    echo "   ✅ .env 파일이 이미 존재합니다"
fi

# 필수 디렉토리 확인
mkdir -p 01_Library/inbox 01_Library/archive 02_Brain/vector_db
echo "   ✅ 디렉토리 구조 확인됨"

# ─────────────────────────────────────────────────────────────────
# 4. Docker 빌드 및 실행
# ─────────────────────────────────────────────────────────────────
echo ""
echo "📦 Step 4/4: Docker 컨테이너 빌드 중..."
echo "   ⏳ 최초 실행 시 5-10분 소요될 수 있습니다..."
echo ""

# 기존 컨테이너 정리
docker compose down 2>/dev/null

# 빌드 및 실행
if docker compose build; then
    echo ""
    echo "   ✅ 빌드 완료"

    if docker compose up -d; then
        echo "   ✅ 컨테이너 시작 완료"
    else
        echo ""
        echo "❌ 컨테이너 시작 실패"
        read -p "엔터를 누르면 종료합니다..."
        exit 1
    fi
else
    echo ""
    echo "❌ Docker 빌드 실패"
    echo "   로그를 확인하세요: docker compose logs"
    read -p "엔터를 누르면 종료합니다..."
    exit 1
fi

# ─────────────────────────────────────────────────────────────────
# 완료
# ─────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ 설치 완료!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📖 사용법:"
echo ""
echo "   1. PDF 추가하기"
echo "      → 01_Library/inbox/ 폴더에 PDF를 넣으세요"
echo ""
echo "   2. 서재 업데이트하기"
echo "      → Claude Desktop/Antigravity에서:"
echo "        '내 서재 업데이트해줘' 라고 말하세요"
echo ""
echo "   3. 검색하기"
echo "      → '신학 DB에서 은총에 대해 검색해줘'"
echo ""
echo "─────────────────────────────────────────────────────────────────"
echo "🔧 관리 명령어:"
echo ""
echo "   상태 확인: docker compose ps"
echo "   로그 보기: docker compose logs -f"
echo "   중지하기:  docker compose down"
echo "   재시작:    docker compose restart"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""

read -p "엔터를 누르면 창을 닫습니다..."
