# Theology AI Lab 빠른 시작

**로컬에 책을 넣고, 로컬에서 인덱싱하고, 로컬에서 검색합니다.**

## 1. 프로그램 설치

압축을 푼 프로젝트 폴더에서 설치 스크립트를 실행합니다.

- Mac: `1_INSTALL_MAC.command`
- Windows: `1_INSTALL_WIN.bat`

설치가 끝나면 다음 폴더가 준비됩니다.

```text
01_Library/inbox
01_Library/archive
02_Brain/vector_db
```

## 2. 앱 실행

- Mac: `3_START_MAC.command`
- Windows: `3_START_WIN.bat`

브라우저에서 `http://localhost:8501`이 열립니다.

## 3. 자료 넣기

`01_Library/inbox`에 PDF, EPUB, TXT 파일을 넣습니다.

하위 폴더를 만들어도 됩니다.

```text
01_Library/inbox/
├── general/
├── dictionaries/
└── commentaries/
```

## 4. 메타데이터 보정

앱의 **Inbox** 탭에서 파일을 선택하고 저자, 제목, 연도, 문서 유형, 실제 페이지 시작 번호를 보정할 수 있습니다.

저장하면 파일 옆에 sidecar JSON이 생성되고, 로컬 인덱서가 이 값을 우선 사용합니다.

## 5. 로컬 인덱싱

**Inbox > 로컬 인덱싱 시작**을 누릅니다.

처리 결과:

- 청크 JSON: `01_Library/archive`
- ChromaDB: `02_Brain/vector_db`
- 처리 완료 원본: Inbox에서 제거됨

## 6. 검색

**검색** 탭에서 질문하거나 키워드를 입력합니다.

- 3중 언어 확장: 한국어 질의를 영어/독일어 신학 용어로 확장
- 이중 검색: ChromaDB 벡터 검색 + archive JSON 키워드 검색
- AI 분석: API 키를 설정한 경우 Claude/GPT/Gemini로 리포트 생성

## 문제 해결

- 앱이 안 열리면 설치 스크립트를 먼저 실행했는지 확인하세요.
- OCR이 필요한 스캔 PDF는 Tesseract와 언어팩이 별도로 필요할 수 있습니다.
- 검색 결과가 없으면 먼저 Inbox에서 로컬 인덱싱을 완료했는지 확인하세요.
