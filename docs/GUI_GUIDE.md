# Theology AI Lab 사용자 가이드 (Local Edition)

## 개요

Local Edition은 Colab과 Google Drive 동기화를 기본 흐름에서 제거했습니다. 자료 입고, 메타데이터 보정, 인덱싱, 검색이 모두 로컬 앱 안에서 이루어집니다.

## 1. 자료 등록

1. `01_Library/inbox`에 PDF/EPUB/TXT 파일을 넣습니다.
2. 앱의 **Inbox** 탭을 엽니다.
3. 필요하면 메타데이터 편집기에서 저자, 제목, 연도, 문서 유형, 실제 페이지 시작 번호를 저장합니다.

## 2. 로컬 인덱싱

**Inbox > 로컬 인덱싱 시작**을 누르면 현재 컴퓨터에서 인덱싱이 실행됩니다.

처리 결과:

- `01_Library/archive`: 청크 JSON과 sidecar metadata 보관
- `02_Brain/vector_db`: ChromaDB 벡터 데이터베이스

## 3. 검색

**검색** 탭에서 질의합니다.

- 3중 언어 확장: 한/영/독 신학 용어 확장
- 이중 검색: 벡터 검색과 JSON 키워드 검색 병행
- AI 분석: API 키가 있으면 검색 결과 기반 리포트 생성

## 4. 설정

- **로컬 서재 경로**: 기본값은 프로젝트 폴더입니다. 외장 SSD 등 다른 로컬 경로도 지정할 수 있습니다.
- **DB 초기화**: ChromaDB 폴더만 삭제하고 archive JSON은 보존합니다.
- **Obsidian 연동**: 검색 결과와 AI 리포트를 지정한 Vault에 저장합니다.

## 주의사항

- 스캔 PDF OCR은 Python 패키지 외에 Tesseract 실행 파일과 언어팩이 필요할 수 있습니다.
- 큰 PDF를 처음 인덱싱할 때는 BGE-M3 모델 다운로드와 임베딩 생성 때문에 시간이 걸릴 수 있습니다.
