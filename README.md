# ☁️ Theology AI Lab v4.0 (Cloud Edition)

> **"무거운 처리는 클라우드에서, 검색은 내 맥북에서."**

개인용 AI 기반 신학 연구 도구의 완성형입니다.  
**Google Colab**의 강력한 GPU로 수천 페이지의 신학 서적(PDF)을 인덱싱하고,  
**Local Streamlit App**으로 내 서재처럼 쾌적하게 검색하세요.

![Cloud Architecture](https://via.placeholder.com/800x200?text=Architecture:+PDF+%E2%86%92+Google+Drive+%E2%86%92+Colab(GPU)+%E2%86%92+Vector+DB+%E2%86%92+Local+App)

---

## ✨ 핵심 기능

1.  **🏭 Cloud Indexing Factory**: 
    - 내 로컬 컴퓨터를 혹사시키지 마세요.
    - **Google Colab (T4 GPU)**를 사용하여 무료로, 빠르게 인덱싱합니다.
    - PDF, EPUB, TXT 등 다양한 형식을 지원합니다.

2.  **☁️ Cloud Storage**:
    - 모든 데이터(원본, 벡터 DB)는 **Google Drive**에 안전하게 저장됩니다.
    - 사무실, 집, 카페 어디서든 같은 데이터를 공유합니다.

3.  **🖥️ Local Insight Viewer**:
    - 가볍고 빠른 로컬 앱(Streamlit)에서 데이터를 검색합니다.
    - **3중 언어 확장** (한글 질문 → 독어/영어 검색)
    - **듀얼 검색** (Vector + Keyword)

---

## 🛠️ 설치 및 설정 (10분 완성)

### 1단계: 구글 드라이브 준비
1. 구글 드라이브에 `Theology_AI_LAB` 폴더를 만듭니다.
2. 다음 구조로 폴더를 만듭니다:
   ```text
   Theology_AI_LAB/
   ├── 01_Library/
   │   ├── inbox/      (여기에 PDF를 넣으세요)
   │   └── archive/    (처리된 파일이 보관됩니다)
   ├── 02_Brain/
   │   └── vector_db/  (두뇌가 여기에 저장됩니다)
   └── 03_System/      (코드 폴더)
   ```

### 2단계: 클라우드 인덱서 준비
1. 제공된 `Theology_AI_Cloud_Indexer.ipynb` 파일을 구글 드라이브 `Theology_AI_LAB` 폴더에 넣습니다.
2. `03_System` 폴더도 통째로 구글 드라이브에 복사합니다.

### 3단계: 로컬 뷰어 설정
1. 이 저장소를 로컬(Mac/PC)에 다운로드합니다.
2. `.env` 파일을 생성하고 다음 내용을 입력합니다:
   ```ini
   # 구글 드라이브 경로 (자신의 환경에 맞게 수정)
   # Mac 예시: /Users/사용자명/Library/CloudStorage/GoogleDrive-이메일/내 드라이브/Theology_AI_LAB
   
   INBOX_DIR=/Users/username/Library/CloudStorage/GoogleDrive-email/내 드라이브/Theology_AI_LAB/01_Library/inbox
   ARCHIVE_DIR=/Users/username/Library/CloudStorage/GoogleDrive-email/내 드라이브/Theology_AI_LAB/01_Library/archive
   DB_PATH=/Users/username/Library/CloudStorage/GoogleDrive-email/내 드라이브/Theology_AI_LAB/02_Brain/vector_db
   
   # AI API 키 (선택 사항)
   ANTHROPIC_API_KEY=sk-...
   ```
3. 실행 스크립트(`Run_App.command`)를 클릭합니다.

---

## 🚀 사용 흐름 (Workflow)

### 1. 자료 등록 (In the Cloud)
1. **Drop**: PDF 파일을 로컬의 `inbox` 폴더에 넣습니다. (구글 드라이브 자동 동기화)
2. **Run**: [Google Colab](https://colab.research.google.com)에서 `Theology_AI_Cloud_Indexer.ipynb`를 열고 **`모두 실행`**을 누릅니다.
3. **Done**: 인덱싱이 끝나면 파일이 `archive`로 이동합니다.

### 2. 자료 검색 (On Local)
1. 로컬 앱(`http://localhost:8501`)을 엽니다.
2. 새로고침(`R`) 하면 방금 인덱싱된 자료가 검색됩니다.
3. AI 리포트 생성, Obsidian 내보내기 등을 수행합니다.

---

## 🏗️ 폴더 구조

```text
Theology_AI_Lab_v4/
├── 03_System/          # 뷰어 소스 코드 (Streamlit)
├── .env                # 개인 설정 (경로, API 키)
├── Theology_AI_Cloud_Indexer.ipynb  # Colab 실행용 노트북
└── docs/               # 상세 매뉴얼
```

---

## 📝 라이센스 및 정보
- **Developer**: Kerygma Press (mitmirsein)
- **Version**: 4.0.0 Cloud Edition
