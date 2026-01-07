@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM ═══════════════════════════════════════════════════════════════════
REM Theology AI Lab v2 - One-Click Installer (Windows)
REM ═══════════════════════════════════════════════════════════════════
REM 사용법: 이 파일을 더블클릭하세요
REM ═══════════════════════════════════════════════════════════════════

echo.
echo ═══════════════════════════════════════════════════════════════
echo 🚀 Theology AI Lab v2 설치를 시작합니다...
echo ═══════════════════════════════════════════════════════════════
echo.

REM ─────────────────────────────────────────────────────────────────
REM 1. Docker Desktop 확인
REM ─────────────────────────────────────────────────────────────────
echo 📦 Step 1/4: Docker Desktop 확인 중...

where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ❌ Docker Desktop이 설치되어 있지 않습니다.
    echo.
    echo 👉 Docker Desktop 다운로드 페이지를 엽니다...
    start https://www.docker.com/products/docker-desktop/
    echo.
    echo ⚠️  Docker Desktop을 설치한 후, 이 스크립트를 다시 실행하세요.
    echo.
    pause
    exit /b 1
)

echo    ✅ Docker 명령어 확인됨

REM ─────────────────────────────────────────────────────────────────
REM 2. Docker 실행 상태 확인
REM ─────────────────────────────────────────────────────────────────
echo.
echo 📦 Step 2/4: Docker 실행 상태 확인 중...

docker info >nul 2>nul
if %errorlevel% neq 0 (
    echo    ⚠️  Docker가 실행 중이 아닙니다. 실행합니다...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

    echo    ⏳ Docker 시작 대기 중...
    set attempt=0

    :WAIT_DOCKER
    timeout /t 2 /nobreak >nul
    docker info >nul 2>nul
    if %errorlevel% equ 0 goto DOCKER_READY

    set /a attempt+=1
    if %attempt% geq 60 (
        echo.
        echo ❌ Docker 시작 시간 초과. Docker Desktop을 수동으로 실행해주세요.
        pause
        exit /b 1
    )
    echo|set /p="."
    goto WAIT_DOCKER
)

:DOCKER_READY
echo    ✅ Docker 실행 중

REM ─────────────────────────────────────────────────────────────────
REM 3. 환경 설정
REM ─────────────────────────────────────────────────────────────────
echo.
echo 📦 Step 3/4: 환경 설정 중...

if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo    ✅ .env 파일 생성 완료
    ) else (
        echo    ⚠️  .env.example 파일이 없습니다. 기본 설정을 사용합니다.
    )
) else (
    echo    ✅ .env 파일이 이미 존재합니다
)

REM 필수 디렉토리 확인
if not exist "01_Library\inbox" mkdir "01_Library\inbox"
if not exist "01_Library\archive" mkdir "01_Library\archive"
if not exist "02_Brain\vector_db" mkdir "02_Brain\vector_db"
echo    ✅ 디렉토리 구조 확인됨

REM ─────────────────────────────────────────────────────────────────
REM 4. Docker 빌드 및 실행
REM ─────────────────────────────────────────────────────────────────
echo.
echo 📦 Step 4/4: Docker 컨테이너 빌드 중...
echo    ⏳ 최초 실행 시 5-10분 소요될 수 있습니다...
echo.

REM 기존 컨테이너 정리
docker compose down >nul 2>nul

REM 빌드 및 실행
docker compose build
if %errorlevel% neq 0 (
    echo.
    echo ❌ Docker 빌드 실패
    echo    로그를 확인하세요: docker compose logs
    pause
    exit /b 1
)

echo.
echo    ✅ 빌드 완료

docker compose up -d
if %errorlevel% neq 0 (
    echo.
    echo ❌ 컨테이너 시작 실패
    pause
    exit /b 1
)

echo    ✅ 컨테이너 시작 완료

REM ─────────────────────────────────────────────────────────────────
REM 완료
REM ─────────────────────────────────────────────────────────────────
echo.
echo ═══════════════════════════════════════════════════════════════
echo ✅ 설치 완료!
echo ═══════════════════════════════════════════════════════════════
echo.
echo 📖 사용법:
echo.
echo    1. PDF 추가하기
echo       → 01_Library\inbox\ 폴더에 PDF를 넣으세요
echo.
echo    2. 서재 업데이트하기
echo       → Claude Desktop/Antigravity에서:
echo         '내 서재 업데이트해줘' 라고 말하세요
echo.
echo    3. 검색하기
echo       → '신학 DB에서 은총에 대해 검색해줘'
echo.
echo ─────────────────────────────────────────────────────────────────
echo 🔧 관리 명령어:
echo.
echo    상태 확인: docker compose ps
echo    로그 보기: docker compose logs -f
echo    중지하기:  docker compose down
echo    재시작:    docker compose restart
echo.
echo ═══════════════════════════════════════════════════════════════
echo.

pause
