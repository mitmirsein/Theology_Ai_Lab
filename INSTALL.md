# Theology AI Lab v2 - 설치 가이드

## 시스템 요구사항

| 항목 | Mac | Windows |
|------|-----|---------|
| OS | macOS 10.15+ | Windows 10+ |
| Docker Desktop | 필수 | 필수 |
| 저장 공간 | 2GB+ | 2GB+ |
| RAM | 8GB+ 권장 | 8GB+ 권장 |

---

## 1단계: Docker Desktop 설치

Theology AI Lab은 Docker 위에서 실행됩니다.

### 다운로드
- https://www.docker.com/products/docker-desktop/

### 설치 확인
```bash
docker --version
# Docker version 24.0.0 이상
```

---

## 2단계: Theology AI Lab 설치

### Mac

1. `Theology_AI_Lab_v2.0.0.dmg` 더블클릭
2. 열린 창에서 `Theology AI Lab` 폴더를 원하는 위치로 드래그
   - 권장: `~/Documents/Theology AI Lab`
3. 복사된 폴더에서 `Theology AI Lab 설치.app` 더블클릭
4. "확인되지 않은 개발자" 경고 시:
   - 마우스 우클릭 → **열기** 선택

### Windows

1. `Theology_AI_Lab_v2.0.0_Setup.exe` 실행
2. 설치 마법사 진행 (기본 경로 또는 원하는 위치 선택)
3. 설치 완료 후 **설치 시작** 체크박스 선택
4. Docker 미설치 경고 시 Docker Desktop 먼저 설치

---

## 3단계: 초기 설정

설치 스크립트가 자동으로 수행하는 작업:

1. Docker Desktop 실행 확인
2. 환경 설정 파일 생성 (`.env`)
3. AI 컨테이너 빌드 (최초 5-10분 소요)
4. 서비스 시작

**"설치 완료" 메시지**가 나오면 준비 완료입니다.

---

## 폴더 구조

```
Theology AI Lab/
├── 01_Library/
│   ├── inbox/      ← PDF 파일을 여기에 넣으세요
│   └── archive/    ← 처리된 파일 보관 (삭제 금지)
├── 02_Brain/
│   └── vector_db/  ← AI 검색 데이터베이스
├── 03_System/      ← 시스템 파일 (수정 금지)
└── README.md
```

---

## 다음 단계

설치가 완료되면 [사용 가이드](USAGE.md)를 참조하세요.
