#!/bin/bash
# ============================================================================
# Theology AI Lab v2 - Mac DMG 빌드 스크립트
# ============================================================================
#
# 사용법:
#   ./build_mac_dmg.sh
#
# 요구사항:
#   - create-dmg (brew install create-dmg)
#   - macOS 10.15+
#
# ============================================================================

set -e

# 설정
APP_NAME="Theology AI Lab"
VERSION="2.0.0"
DMG_NAME="Theology_AI_Lab_v${VERSION}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${SCRIPT_DIR}/build"
DIST_DIR="${SCRIPT_DIR}/dist"

echo "=============================================="
echo "🏗️  ${APP_NAME} v${VERSION} DMG 빌드"
echo "=============================================="

# 빌드 디렉토리 초기화
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${BUILD_DIR}/${APP_NAME}"
mkdir -p "${DIST_DIR}"

echo "📦 프로젝트 파일 복사 중..."

# 필요한 파일들 복사
cp -r "${PROJECT_ROOT}/01_Library" "${BUILD_DIR}/${APP_NAME}/"
cp -r "${PROJECT_ROOT}/02_Brain" "${BUILD_DIR}/${APP_NAME}/"
cp -r "${PROJECT_ROOT}/03_System" "${BUILD_DIR}/${APP_NAME}/"
cp "${PROJECT_ROOT}/docker-compose.yml" "${BUILD_DIR}/${APP_NAME}/"
cp "${PROJECT_ROOT}/.env.example" "${BUILD_DIR}/${APP_NAME}/"
cp "${PROJECT_ROOT}/README.md" "${BUILD_DIR}/${APP_NAME}/"

# 설치 스크립트 복사 및 .app으로 래핑
cp "${PROJECT_ROOT}/INSTALL_ONECLICK.command" "${BUILD_DIR}/${APP_NAME}/"

# 런처 앱 생성 (AppleScript 기반)
echo "🍎 런처 앱 생성 중..."

LAUNCHER_DIR="${BUILD_DIR}/${APP_NAME}/Theology AI Lab 설치.app/Contents/MacOS"
mkdir -p "${LAUNCHER_DIR}"
mkdir -p "${BUILD_DIR}/${APP_NAME}/Theology AI Lab 설치.app/Contents/Resources"

# Info.plist 생성
cat > "${BUILD_DIR}/${APP_NAME}/Theology AI Lab 설치.app/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIdentifier</key>
    <string>com.kerygma.theology-ai-lab</string>
    <key>CFBundleName</key>
    <string>Theology AI Lab 설치</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
</dict>
</plist>
PLIST

# 런처 스크립트 생성
cat > "${LAUNCHER_DIR}/launcher" << 'LAUNCHER'
#!/bin/bash
cd "$(dirname "$0")/../../.."
./INSTALL_ONECLICK.command
LAUNCHER

chmod +x "${LAUNCHER_DIR}/launcher"

# 아이콘 생성 (텍스트 기반 임시 아이콘)
# 실제 배포 시에는 .icns 파일로 교체 필요

# .DS_Store 및 불필요 파일 제거
find "${BUILD_DIR}" -name ".DS_Store" -delete
find "${BUILD_DIR}" -name "*.pyc" -delete
find "${BUILD_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true
rm -rf "${BUILD_DIR}/${APP_NAME}/03_System/venv" 2>/dev/null || true

# create-dmg 설치 확인
if ! command -v create-dmg &> /dev/null; then
    echo "⚠️  create-dmg가 설치되어 있지 않습니다."
    echo "   설치: brew install create-dmg"
    echo ""
    echo "   대안: 수동 DMG 생성"

    # 수동 DMG 생성
    echo "📀 DMG 생성 중 (hdiutil)..."
    hdiutil create -volname "${APP_NAME}" \
        -srcfolder "${BUILD_DIR}/${APP_NAME}" \
        -ov -format UDZO \
        "${DIST_DIR}/${DMG_NAME}.dmg"
else
    echo "📀 DMG 생성 중 (create-dmg)..."

    create-dmg \
        --volname "${APP_NAME}" \
        --volicon "${SCRIPT_DIR}/resources/icon.icns" 2>/dev/null || true \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "Theology AI Lab 설치.app" 150 190 \
        --icon "01_Library" 350 190 \
        --icon "README.md" 450 190 \
        --hide-extension "Theology AI Lab 설치.app" \
        --app-drop-link 500 190 \
        "${DIST_DIR}/${DMG_NAME}.dmg" \
        "${BUILD_DIR}/${APP_NAME}" \
        2>/dev/null || \
    hdiutil create -volname "${APP_NAME}" \
        -srcfolder "${BUILD_DIR}/${APP_NAME}" \
        -ov -format UDZO \
        "${DIST_DIR}/${DMG_NAME}.dmg"
fi

# 정리
rm -rf "${BUILD_DIR}"

echo ""
echo "=============================================="
echo "✅ DMG 빌드 완료!"
echo "=============================================="
echo "📍 파일: ${DIST_DIR}/${DMG_NAME}.dmg"
echo ""
echo "📋 DMG 내용물:"
echo "   - Theology AI Lab 설치.app (더블클릭으로 설치)"
echo "   - 01_Library/ (PDF 저장 폴더)"
echo "   - README.md (사용 설명서)"
echo "=============================================="
