# 📦 Theology AI Lab 패키징 가이드

## 개요

이 디렉토리에는 Theology AI Lab의 배포용 인스톨러를 생성하는 스크립트가 포함되어 있습니다.

---

## 🍎 Mac: DMG 빌드

### 요구사항
- macOS 10.15+
- (선택) `create-dmg` - 더 예쁜 DMG 생성
  ```bash
  brew install create-dmg
  ```

### 빌드 방법
```bash
cd packaging
chmod +x build_mac_dmg.sh
./build_mac_dmg.sh
```

### 결과물
```
dist/Theology_AI_Lab_v2.0.0.dmg
```

### DMG 내용물
- `Theology AI Lab 설치.app` - 더블클릭으로 설치 시작
- `01_Library/` - PDF 저장 폴더
- `README.md` - 사용 설명서

---

## 🪟 Windows: EXE 빌드 (Inno Setup)

### 요구사항
- Windows 10+
- [Inno Setup](https://jrsoftware.org/isinfo.php) (무료)

### 빌드 방법
1. Inno Setup Compiler 설치
2. `packaging/windows/theology_ai_lab.iss` 파일 열기
3. Build → Compile (Ctrl+F9)

### 결과물
```
dist/Theology_AI_Lab_v2.0.0_Setup.exe
```

### 설치 마법사 기능
- Docker Desktop 설치 여부 확인 (미설치 시 경고)
- 시작 메뉴 바로가기 생성
- 바탕화면 아이콘 생성 (선택)
- 설치 후 자동 실행 옵션

---

## 📁 디렉토리 구조

```
packaging/
├── build_mac_dmg.sh          # Mac DMG 빌드 스크립트
├── windows/
│   └── theology_ai_lab.iss   # Inno Setup 스크립트
├── resources/
│   ├── icon.icns             # Mac 앱 아이콘 (추가 필요)
│   └── icon.ico              # Windows 앱 아이콘 (추가 필요)
├── dist/                     # 빌드 결과물 (자동 생성)
└── README.md                 # 이 파일
```

---

## 🎨 아이콘 준비

배포 전 아이콘 파일을 준비해야 합니다:

### Mac (.icns)
```bash
# PNG에서 icns 생성 (1024x1024 권장)
mkdir icon.iconset
sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png
iconutil -c icns icon.iconset -o icon.icns
```

### Windows (.ico)
- [RealFaviconGenerator](https://realfavicongenerator.net/) 또는
- ImageMagick: `convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico`

---

## 🚀 배포 체크리스트

### 빌드 전
- [ ] 버전 번호 확인 (`build_mac_dmg.sh`, `theology_ai_lab.iss`)
- [ ] 아이콘 파일 준비 (`resources/`)
- [ ] README.md 최신화
- [ ] `.env.example` 확인

### Mac DMG
- [ ] `./build_mac_dmg.sh` 실행
- [ ] DMG 마운트 후 설치 테스트
- [ ] Docker 미설치 환경에서 테스트

### Windows EXE
- [ ] Inno Setup으로 컴파일
- [ ] 설치 마법사 테스트
- [ ] Docker 미설치 환경에서 경고 확인

### 최종 확인
- [ ] 전체 설치 → 사용 흐름 테스트
- [ ] PDF 처리 테스트
- [ ] Claude Desktop 연동 테스트

---

## ⚠️ 중요 사항

### Docker Desktop 필수
- 이 앱은 Docker Desktop이 **필수**입니다
- 인스톨러는 Docker를 포함하지 않습니다 (라이선스 제약)
- 설치 시 Docker 미설치 경고를 표시합니다

### 서명 (선택)
- **Mac**: 공증(Notarization) 없이 배포 시 "확인되지 않은 개발자" 경고
  - 해결: Apple Developer Program 가입 후 서명/공증
  - 임시: 사용자가 시스템 환경설정 → 보안에서 허용

- **Windows**: 서명 없이 배포 시 SmartScreen 경고
  - 해결: 코드 서명 인증서 구매 후 서명
  - 임시: 사용자가 "추가 정보" → "실행" 클릭

---

> **Made by [케리그마출판사](https://www.kerygma.co.kr)**
