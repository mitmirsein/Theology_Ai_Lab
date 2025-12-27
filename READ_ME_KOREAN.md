# 📖 Theology AI Lab: 사용자 매뉴얼 (User Guide)

> **"내 컴퓨터에 신학 연구소를 차리다."**
> Theology AI Lab은 인공지능(Antigravity)과 함께 신학 원전을 연구할 수 있는 개인용 디지털 서재입니다.

---

## 0. 🛠️ 준비물 (Prerequisites)

이 키트를 사용하려면 **Antigravity (또는 VS Code)** 가 먼저 설치되어 있어야 합니다.
*   아직 없다면? 👉 [다운로드 페이지로 가기](https://antigravity.ai)

---

## 1. 🚀 설치 및 시작 (Installation)

1.  **압축 해제:** `Theology_AI_Lab.zip`을 원하는 곳(예: 바탕화면)에 풉니다.
2.  **설치 (OS에 맞는 파일 실행):**
    *   🍎 **Mac:** `1_INSTALL_MAC.command`
    *   🪟 **Windows:** `1_INSTALL_WIN.bat`
    *   **자동 수행:** 가상환경을 만들고 필요한 AI 라이브러리를 자동으로 설치합니다.
    *   "설치 완료" 메시지가 나오면 준비 끝입니다.

---

## 2. 📚 데이터 공장 가동 (Local Pipeline)

여러분이 가진 PDF나 텍스트 자료를 AI가 읽을 수 있는 형태로 변환합니다.

### 1단계: 자료 넣기
*   `01_Library/inbox` 폴더에 PDF 파일이나 텍스트 파일을 넣으세요.
*   *(팁: 파일명에 영문을 권장합니다. 예: `Barth_Dogmatics.pdf`)*

### 2단계: 공장 가동
*   `2_PROCESS_DATA.command` 파일을 더블 클릭하세요. (Mac/Win 공용)
*   **자동 수행 작업:**
    1.  **변환:** 텍스트를 추출하고 분석하기 좋은 단위로 자릅니다(Chunking).
    2.  **보존:** 원본 텍스트는 `01_Library/archive`에 안전하게 보관됩니다. (표제어 검색용)
    3.  **학습:** AI 두뇌(`02_Brain`)에 내용을 입력합니다. (의미 검색용)

---

## 3. 🤖 연구 수행 (Antigravity Integration)

이제 AI와 대화하며 연구를 시작할 수 있습니다.

1.  **서버 켜기:** `3_START_SERVER.command`를 실행합니다.
2.  **Antigravity에서 질문하기:**

> **"신학 DB에서 '칭의(Justification)'에 대한 내용을 검색해줘."**

> **"RGG 사전에서 'Moses' 항목을 찾아줘."**

AI는 두 가지 방식으로 동시에 자료를 찾습니다:
*   **의미 검색 (Vector Search):** 단어가 달라도 문맥이 비슷한 내용을 찾아냅니다. (Brain 활용)
*   **표제어 검색 (Lemma Search):** 정확한 사전 항목을 찾아냅니다. (Library 활용)

---

## 4. 📁 폴더 구조 안내

여러분이 관리해야 할 폴더는 딱 하나입니다.

*   📂 **01_Library**: 서재
    *   📥 `inbox`: 새 책을 넣는 곳 (작업 후 비워집니다)
    *   📚 `archive`: 정리된 책이 보관되는 곳 (지우지 마세요!)

*   *나머지 `02_Brain`, `03_System` 폴더는 AI가 관리하는 영역이므로 건드리지 않아도 됩니다.*
