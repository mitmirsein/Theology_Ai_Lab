#!/usr/bin/env python3
"""
Theology AI Lab - Streamlit GUI
================================
로컬 신학 연구 데이터베이스 인터페이스

실행: streamlit run app.py
"""

import os

# tokenizers fork 크래시 방지 (멀티스레드 환경에서 subprocess 호출 시 충돌 방지)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import sys
import json
import shutil
import re
from pathlib import Path
from datetime import datetime

import streamlit as st
import logging

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("App")

# 경로 설정
SCRIPT_DIR = Path(__file__).parent.absolute()
KIT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR / "utils"))

# 환경 변수 로드
from dotenv import load_dotenv
ENV_FILE = KIT_ROOT / ".env"
load_dotenv(ENV_FILE)

# 전역 설정 로드
def load_global_settings():
    settings = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
        "RAG_MODEL": os.getenv("RAG_MODEL", "gemini-2.5-flash"),
        "RAG_MAX_TOKENS": os.getenv("RAG_MAX_TOKENS", "4096"),
        "APP_TITLE": os.getenv("APP_TITLE", "Kerygma Th Library"),
        "OBSIDIAN_VAULT": os.getenv("OBSIDIAN_VAULT", ""),
    }
    # .env 파일이 있으면 우선적으로 덮어쓰기 (실시간 반영용)
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key in settings:
                        settings[key] = value
    return settings

GLOBAL_SETTINGS = load_global_settings()
APP_TITLE = GLOBAL_SETTINGS["APP_TITLE"]

# 경로 설정 (상대 경로는 KIT_ROOT 기준으로 변환)
def resolve_path(env_var: str, default: str) -> Path:
    """환경 변수 경로를 절대 경로로 변환"""
    val = os.getenv(env_var, default)
    if val is None:
        val = default
    if val.startswith("."):
        return (KIT_ROOT / val).resolve()
    return Path(val)

INBOX_DIR = resolve_path("INBOX_DIR", "./01_Library/inbox")
ARCHIVE_DIR = resolve_path("ARCHIVE_DIR", "./01_Library/archive")
DB_PATH = resolve_path("CHROMA_DB_DIR", "./02_Brain/vector_db")
LEMMA_INDEX_PATH = ARCHIVE_DIR / "lemma_index.json"

# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 캐시된 리소스 로드
# ============================================================
@st.cache_resource
def load_embedder():
    """BGE-M3 임베딩 모델 로드 (M1 가속 지원)"""
    from pipeline.embedder import TheologyEmbedder
    return TheologyEmbedder()

@st.cache_resource
def load_searcher(_db_path: str):
    """Hybrid 검색 엔진 로드"""
    from pipeline.searcher import TheologySearcher
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
    
    # 임베딩 모델 로드
    embedder = load_embedder()
    
    # Chroma DB 연결 (embedder 객체 직접 전달)
    vector_db = Chroma(
        persist_directory=_db_path,
        embedding_function=embedder,
        collection_name="theology_library"
    )
    
    searcher = TheologySearcher(vector_db)
    
    # BM25 구성을 위해 전체 문서 로드 (하이브리드 검색용)
    try:
        results = vector_db.get(include=["documents", "metadatas"])
        if results and results["documents"]:
            all_docs = [
                Document(page_content=d, metadata=m) 
                for d, m in zip(results["documents"], results["metadatas"])
            ]
            searcher.build_ensemble(all_docs)
    except Exception as e:
        logger.error(f"Failed to build ensemble: {e}")
        
    return searcher

@st.cache_resource
def load_query_expander():
    """3중 언어 쿼리 확장기 로드"""
    try:
        from utils.query_expander import QueryExpander
        return QueryExpander()
    except ImportError:
        return None

@st.cache_resource
def load_db(_db_path: str):
    """ChromaDB 연결"""
    import chromadb
    db_path = Path(_db_path)
    if not db_path.exists():
        return None, None
    
    try:
        client = chromadb.PersistentClient(path=_db_path)
        collection = client.get_collection(name="theology_library")
        # [v4.0.1] DB 무결성 확인 (Reset 직후 테이블 없음 에러 방지)
        _ = collection.count() 
        return client, collection
    except Exception:
        return None, None

@st.cache_data(ttl=60)
def load_lemma_index(_index_path: str):
    """Lemma 인덱스 로드 (v1.0 및 v2.0 형식 모두 지원)"""
    index_path = Path(_index_path)
    if not index_path.exists():
        return None
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # v2.0 형식인지 확인 (entries 키가 있는지)
    if "entries" in data:
        return data

    # v1.0 형식 → v2.0 형식으로 변환
    # v1.0: {"lemma": [{file, page}, ...], ...}
    # v2.0: {"entries": {...}, "by_category": {}, "by_source": {...}, "updated_at": ...}
    entries = {}
    by_source = {}

    for lemma, occurrences in data.items():
        entries[lemma] = []
        for occ in occurrences:
            source_file = occ.get("file", "")
            source_name = source_file.replace(".json", "") if source_file else "Unknown"
            page = occ.get("page", 0)

            entries[lemma].append({
                "file": source_file,
                "page": page,
                "source": source_name
            })

            # by_source 집계
            if source_name not in by_source:
                by_source[source_name] = {"count": 0, "volumes": []}
            by_source[source_name]["count"] += 1

    return {
        "version": "1.0 (converted)",
        "updated_at": datetime.now().isoformat(),
        "entries": entries,
        "by_category": {},  # v1.0에는 카테고리 정보 없음
        "by_source": by_source
    }


def get_sources_from_db() -> dict:
    """
    ChromaDB에서 직접 소스 목록과 청크 수 조회

    Returns:
        {"source_name": {"count": int}, ...}
    """
    import chromadb
    from collections import defaultdict

    try:
        client = chromadb.PersistentClient(path=str(DB_PATH))
        collection = client.get_collection(name="theology_library")
        _ = collection.count() # Health check
    except Exception:
        return {}

    # 모든 문서의 메타데이터 조회
    results = collection.get(include=["metadatas"])

    if not results.get("metadatas"):
        return {}

    # 소스별 집계
    source_counts = defaultdict(int)
    for meta in results["metadatas"]:
        source = meta.get("source", "Unknown")
        source_counts[source] += 1

    return {source: {"count": count} for source, count in source_counts.items()}


def delete_source_from_db(source_name: str) -> int:
    """
    ChromaDB에서 특정 소스의 모든 청크 삭제

    Args:
        source_name: 삭제할 소스 이름 (예: "TRE_Bd04")

    Returns:
        삭제된 청크 수
    """
    import chromadb

    try:
        client = chromadb.PersistentClient(path=str(DB_PATH))
        collection = client.get_collection(name="theology_library")
        _ = collection.count() # Health check
    except Exception:
        return 0

    # 해당 소스의 모든 문서 ID 조회
    results = collection.get(
        where={"source": source_name},
        include=[]
    )

    ids_to_delete = results.get("ids", [])
    if not ids_to_delete:
        return 0

    # 삭제 실행
    collection.delete(ids=ids_to_delete)

    # 캐시 무효화
    load_db.clear()
    load_lemma_index.clear()

    return len(ids_to_delete)


def reindex_source(source_name: str) -> str:
    """
    소스 재인덱싱: DB에서 삭제 후 아카이브에서 다시 인덱싱

    Args:
        source_name: 재인덱싱할 소스 이름

    Returns:
        결과 메시지
    """
    import chromadb
    from sentence_transformers import SentenceTransformer

    # 1. 아카이브 파일 확인
    archive_file = ARCHIVE_DIR / f"{source_name}.json"
    if not archive_file.exists():
        raise FileNotFoundError(f"아카이브 파일 없음: {archive_file}")

    # 2. 기존 데이터 삭제
    deleted_count = delete_source_from_db(source_name)

    # 3. 아카이브에서 데이터 로드
    with open(archive_file, "r", encoding="utf-8") as f:
        first_char = f.read(1)
        f.seek(0)

        if first_char == "[":
            data = json.load(f)
        else:
            raw_data = json.load(f)
            if isinstance(raw_data, dict) and "chunks" in raw_data:
                data = raw_data["chunks"]
            elif isinstance(raw_data, dict):
                data = [raw_data]
            else:
                data = [raw_data]

    if not data:
        return f"삭제 {deleted_count}개, 데이터 없음"

    # 4. 모델 및 DB 연결
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    try:
        client = chromadb.PersistentClient(path=str(DB_PATH))
        collection = client.get_or_create_collection(name="theology_library")
    except Exception as e:
        return f"DB 연결 실패: {e}"

    # 5. 재인덱싱
    documents = []
    ids = []
    metadatas = []

    for item in data:
        unique_id = f"{source_name}_{item.get('id', hash(item.get('text', '')))}"
        meta = item.get("metadata", {})
        meta["source"] = source_name
        meta["indexed_at"] = datetime.now().isoformat()
        meta["reindexed"] = True  # 재인덱싱 표시

        # None 및 리스트 처리
        for k, v in list(meta.items()):
            if v is None:
                meta[k] = ""
            elif isinstance(v, list):
                meta[k] = ", ".join(str(x) for x in v)

        documents.append(item["text"])
        ids.append(unique_id)
        metadatas.append(meta)

    # 배치 처리
    batch_size = 10
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        batch_meta = metadatas[i:i + batch_size]

        embeddings = model.encode(batch_docs).tolist()
        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            embeddings=embeddings,
            metadatas=batch_meta
        )

    # 캐시 무효화
    load_db.clear()
    load_lemma_index.clear()

    return f"삭제 {deleted_count}개 → 새로 인덱싱 {len(documents)}개"


def check_duplicate_source(source_name: str) -> dict:
    """
    중복 인덱싱 여부 확인

    Returns:
        {"exists": bool, "count": int, "indexed_at": str}
    """
    import chromadb

    try:
        client = chromadb.PersistentClient(path=str(DB_PATH))
        collection = client.get_collection(name="theology_library")
        _ = collection.count() # Health check
    except Exception:
        return {"exists": False, "count": 0, "indexed_at": None}

    results = collection.get(
        where={"source": source_name},
        include=["metadatas"],
        limit=1
    )

    if not results.get("ids"):
        return {"exists": False, "count": 0, "indexed_at": None}

    # 전체 개수 조회
    all_results = collection.get(
        where={"source": source_name},
        include=[]
    )

    indexed_at = None
    if results.get("metadatas"):
        indexed_at = results["metadatas"][0].get("indexed_at", "")

    return {
        "exists": True,
        "count": len(all_results.get("ids", [])),
        "indexed_at": indexed_at
    }


# ============================================================
# 사이드바
# ============================================================
# 타이틀 처리 (Theology AI Lab인 경우 분할 표시)
title_main = APP_TITLE
title_sub = ""
if "Theology" in APP_TITLE and "AI Lab" in APP_TITLE:
    title_sub = "Theology"
    title_main = "AI Lab"

# 서브 타이틀 HTML 생성
if title_sub:
    sub_title_html = f'<div style="font-size: 0.8em; font-weight: 700; color: #FFFFFF; text-transform: uppercase; letter-spacing: 2px; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">{title_sub}</div>'
else:
    sub_title_html = ""

# HTML 생성 (완전 인라인 문자열 결합 방식)
sidebar_html = (
    '<div style="text-align: center; padding: 15px 0 25px 0;">'
    '<div style="margin-bottom: 10px;">'
    + sub_title_html +
    f'<div style="font-size: 1.5em; font-weight: 900; color: #FFFFFF; letter-spacing: 0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">{title_main}</div>'
    '</div>'
    '<div style="display: inline-block; background: linear-gradient(135deg, #7C3AED 0%, #6B21A8 100%); color: white; padding: 4px 16px; border-radius: 20px; font-size: 0.7em; font-weight: 700; letter-spacing: 0.5px; box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4);">'
    'v4.0.0'
    '</div>'
    '</div>'
)

st.sidebar.markdown(sidebar_html, unsafe_allow_html=True)

# 하드웨어 정보 표시
embedder = load_embedder()
st.sidebar.info(f" 엔진: BGE-M3 | 가속: {embedder.device.upper()}")

st.sidebar.markdown("---")



page = st.sidebar.radio(
    "메뉴",
    ["🔍 검색", "📊 통계", "⚙️ 설정"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")

# 옵시디언 열기 버튼
if st.sidebar.button("🟣 옵시디언 열기", use_container_width=True):
    # 최신 경로를 가져오기 위해 여러 소스 확인
    vault_path_final = ""
    
    # 1. 세션 스테이트 (설정 페이지에서 입력 중인 값)
    if st.session_state.get("obsidian_vault_input"):
        vault_path_final = st.session_state.get("obsidian_vault_input", "").strip()
    
    # 2. 세션 스테이트의 저장된 설정
    if not vault_path_final and st.session_state.get("current_settings"):
        vault_path_final = st.session_state.current_settings.get("OBSIDIAN_VAULT", "").strip()
    
    # 3. .env 파일 직접 읽기 (최후 수단)
    if not vault_path_final and ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("OBSIDIAN_VAULT="):
                    vault_path_final = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                    break
    
    if vault_path_final:
        import subprocess
        import platform
        from urllib.parse import quote
        
        # 전체 경로를 URL 인코딩하여 사용 (path= 방식)
        path_encoded = quote(vault_path_final)
        obsidian_uri = f"obsidian://open?path={path_encoded}"
        
        vault_name = Path(vault_path_final).name
        st.sidebar.caption(f"🚀 실행: {vault_name}")
        
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", obsidian_uri])
            elif platform.system() == "Windows":
                os.startfile(obsidian_uri)
            else:
                subprocess.run(["xdg-open", obsidian_uri])
        except Exception as e:
            st.sidebar.error(f"실행 실패: {e}")
    else:
        st.sidebar.warning("⚠️ 설정 > Obsidian 경로를 먼저 입력하세요")

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style="text-align: center; font-size: 0.85em; padding-top: 10px;">
        <a href="https://www.kerygma.co.kr" target="_blank" style="color: #6B46C1; text-decoration: none; font-weight: 600; display: inline-flex; align-items: center; gap: 5px;">
            <span>☕</span> 책 한 권 사주셔서 응원해주세요
        </a>
        <br><br>
        <div style="color: #A0AEC0; font-size: 0.8em; line-height: 1.4;">
            © 2025 Kerygma Press
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# AI 리포트 생성 함수
# ============================================================
def generate_ai_report(query: str, context: str, provider: str, model_name: str, api_key: str) -> str:
    """
    검색 결과를 바탕으로 AI가 분석 리포트 생성

    Args:
        query: 검색 질문
        context: 검색 결과 텍스트
        provider: API 프로바이더 (anthropic, openai, google)
        model_name: 모델 이름
        api_key: API 키

    Returns:
        AI 생성 리포트
    """
    system_prompt = """당신은 신학 연구 전문가입니다. 제공된 신학 문헌 자료를 바탕으로 사용자의 질문에 대해 학술적으로 정확하고 깊이 있는 분석을 제공하세요.

규칙:
1. 제공된 자료에 근거하여 답변하세요
2. 출처를 명시하세요 (예: "TRE에 따르면...")
3. 한국어로 답변하세요
4. 학술적 톤을 유지하세요
5. 자료에 없는 내용은 추측하지 마세요"""

    user_prompt = f"""질문: {query}

참고 자료:
{context}

위 자료를 바탕으로 질문에 대한 분석 리포트를 작성해주세요."""

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model_name,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            return response.content[0].text

        elif provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model_name,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.choices[0].message.content

        elif provider == "google":
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=f"{system_prompt}\n\n{user_prompt}",
                config=types.GenerateContentConfig(max_output_tokens=4096)
            )
            return response.text

        else:
            return f"❌ 지원하지 않는 프로바이더: {provider}"

    except Exception as e:
        return f"❌ AI 리포트 생성 실패: {str(e)}"


def get_active_api_config() -> tuple:
    """현재 설정된 API 정보 반환 (provider, model, api_key)"""
    if not ENV_FILE.exists():
        return None, None, None

    settings = {}
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                settings[key.strip()] = value.strip().strip('"').strip("'")

    model_name = settings.get("RAG_MODEL", "")

    # 모델명으로 프로바이더 추론
    if model_name.startswith("claude"):
        provider = "anthropic"
        api_key = settings.get("ANTHROPIC_API_KEY", "")
    elif model_name.startswith("gpt"):
        provider = "openai"
        api_key = settings.get("OPENAI_API_KEY", "")
    elif model_name.startswith("gemini"):
        provider = "google"
        api_key = settings.get("GOOGLE_API_KEY", "")
    else:
        return None, None, None

    if not api_key:
        return None, None, None

    return provider, model_name, api_key


def run_pipeline(chunk_size: int, overlap: int, target_file: str = None):
    """인덱싱 파이프라인 실행 및 실시간 로그 표시"""
    try:
        import subprocess
        
        cmd = [
            sys.executable, 
            str(SCRIPT_DIR / "processor_v4.py"),
            "--inbox", str(INBOX_DIR),
            "--archive", str(ARCHIVE_DIR),
            "--db", str(DB_PATH)
        ]
        
        with st.status(f"🏗️ 인덱싱 파이프라인 가동 중{' (개별 파일)' if target_file else ''}...", expanded=True) as log_status:
            log_output = st.empty()
            prog_container = st.empty()
            current_log = []
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            for line in process.stdout:
                line = line.strip()
                if not line: continue
                
                if "[PROGRESS]" in line:
                    try:
                        # [v2.7.23] 개선된 진행률 파싱 (퍼센트 + 상태 메시지)
                        parts = line.split("[PROGRESS]")[1].strip()
                        pct_str = parts.split("%")[0].strip()
                        prog_val = int(pct_str)
                        # 괄호 이후 또는 % 이후의 메시지 추출
                        if "%" in parts:
                            status_msg = parts.split("%", 1)[1].strip()
                        else:
                            status_msg = ""
                        prog_container.progress(prog_val / 100, f"진행률: {prog_val}% {status_msg}")
                    except:
                        pass
                else:
                    current_log.append(line)
                    log_output.code("\n".join(current_log[-15:]))
                    
            process.wait()
            
            if process.returncode == 0:
                log_status.update(label="✅ 모든 파일 처리 완료!", state="complete", expanded=False)
                st.success("🎉 서재 업데이트가 성공적으로 완료되었습니다.")
                load_db.clear()
                load_lemma_index.clear()
                st.session_state.page_mappings = {}
                
                # [v2.7.23] 완료 후 안내를 위한 세션 상태 설정 및 페이지 새로고침
                st.session_state["pipeline_completed"] = True
                st.rerun()  # 페이지 새로고침으로 상단 안내 패널 표시
            else:
                log_status.update(label="❌ 처리 중 오류 발생", state="error")
                st.error(f"파이프라인 실행 실패 (Exit Code: {process.returncode})")
                
    except Exception as e:
        st.error(f"❌ 시스템 오류: {e}")

# ============================================================
# 검색 페이지
# ============================================================
if page == "🔍 검색":
    st.markdown(f"""
        <div style="padding-bottom: 25px;">
            <h1 style="color: #2D3748; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 0;">🔍 {APP_TITLE} 검색</h1>
            <p style="color: #718096; font-size: 1.1em; font-weight: 400;">기록된 지혜의 바다에서 필요한 문장을 건져올리세요.</p>
        </div>
    """, unsafe_allow_html=True)


    client, collection = load_db(str(DB_PATH))

    if collection is None:
        st.warning("⚠️ 데이터베이스가 비어있습니다. 먼저 파일을 업로드하세요.")
    else:
        # [Cloud Edition] 청크 수는 통계 페이지에서 확인
        pass

        # 검색 입력
        query = st.text_input(
            "검색어를 입력하세요",
            placeholder="예: 칭의, Gnade, Rechtfertigung..."
        )

        # 검색 옵션
        col_opt1, col_opt2, col_opt3 = st.columns([2, 2, 1])
        with col_opt1:
            use_trilingual = st.checkbox("🌐 3중 언어 확장 (한/영/독)", value=True, help="신학 용어를 한국어, 영어, 독일어로 자동 확장합니다")
        with col_opt2:
            use_dual_search = st.checkbox("🔍 이중 검색 (Vector+JSON)", value=True, help="벡터 검색과 키워드 검색을 동시 수행합니다")
        with col_opt3:
            n_results = st.selectbox("결과 수", [5, 10, 20], index=0)

        # 3중 언어 확장 표시
        if query and use_trilingual:
            expander = load_query_expander()
            if expander:
                expanded = expander.expand(query)
                if expanded.matched_concepts:
                    with st.expander(f"🌐 쿼리 확장: {', '.join(expanded.matched_concepts)}", expanded=False):
                        col_lang1, col_lang2, col_lang3 = st.columns(3)
                        with col_lang1:
                            st.caption("🇰🇷 한국어")
                            st.write(", ".join(expanded.korean[:5]))
                        with col_lang2:
                            st.caption("🇺🇸 English")
                            st.write(", ".join(expanded.english[:5]))
                        with col_lang3:
                            st.caption("🇩🇪 Deutsch")
                            st.write(", ".join(expanded.german[:5]))

        if query:
            with st.spinner("검색 중..."):
                # 3중 언어 확장 적용
                search_queries = [query]
                if use_trilingual:
                    expander = load_query_expander()
                    if expander:
                        search_queries = expander.get_embedding_queries(query, max_q=3)
                
                all_results = []
                
                # 이중 검색 모드
                if use_dual_search:
                    try:
                        from utils.dual_search import DualSearchEngine
                        dual_engine = DualSearchEngine(
                            db_path=str(DB_PATH),
                            archive_path=str(ARCHIVE_DIR),
                            use_trilingual=use_trilingual
                        )
                        dual_results = dual_engine.search(query, n_results=n_results * 2)
                        
                        # DualSearchEngine 결과를 Document 형식으로 변환
                        from langchain_core.documents import Document
                        for r in dual_results:
                            doc = Document(
                                page_content=r.content,
                                metadata={
                                    "source": r.source,
                                    "author": r.author,
                                    "doc_type": r.doc_type,
                                    "page": r.page,
                                    "search_method": r.method,
                                    **r.metadata
                                }
                            )
                            all_results.append(doc)
                    except Exception as e:
                        logger.warning(f"Dual search failed, falling back: {e}")
                        use_dual_search = False  # Fallback to normal search
                
                # 일반 벡터 검색 (fallback 또는 이중 검색 비활성화 시)
                if not use_dual_search or not all_results:
                    searcher = load_searcher(str(DB_PATH))
                    for sq in search_queries:
                        results_docs = searcher.search(sq)
                        all_results.extend(results_docs)
                
                # 중복 제거 (content 기준)
                seen_contents = set()
                unique_results = []
                for doc in all_results:
                    content_key = doc.page_content[:100]
                    if content_key not in seen_contents:
                        seen_contents.add(content_key)
                        unique_results.append(doc)
                
                # 기존 결과를 딕셔너리 형태로 변환 (기존 UI 호환성 유지)
                documents = [d.page_content for d in unique_results[:n_results]]
                metadatas = [d.metadata for d in unique_results[:n_results]]
                results = {'documents': [documents], 'metadatas': [metadatas]}

            if results['documents'] and results['documents'][0]:
                st.markdown(f"### 검색 결과 ({len(results['documents'][0])}건)")

                # ─────────────────────────────────────────────────────────
                # 마크다운 리포트 생성 함수
                # ─────────────────────────────────────────────────────────
                def generate_search_report(query: str, results: dict) -> str:
                    """검색 결과를 마크다운 리포트로 변환"""
                    report_lines = [
                        f"# 검색 리포트: {query}",
                        f"",
                        f"**검색일**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        f"**결과 수**: {len(results['documents'][0])}건",
                        f"",
                        "---",
                        "",
                    ]

                    for i, doc in enumerate(results['documents'][0]):
                        meta = results['metadatas'][0][i]
                        source = meta.get('source', 'Unknown')
                        # 메타데이터 키 호환성 처리 (page or page_number)
                        raw_page = meta.get('page', meta.get('page_number', '?'))
                        try:
                            page_num = int(raw_page) + PAGE_OFFSET if str(raw_page).isdigit() else raw_page
                        except:
                            page_num = raw_page
                        
                        lemma = meta.get('lemma', '')
                        category = meta.get('category', '')

                        report_lines.append(f"## [{i+1}] {source} - p.{page_num}")
                        if lemma:
                            report_lines.append(f"**표제어**: {lemma}")
                        if category:
                            report_lines.append(f"**분류**: {category}")
                        report_lines.append("")
                        report_lines.append(doc)
                        report_lines.append("")
                        report_lines.append("---")
                        report_lines.append("")

                    report_lines.append(f"*Generated by {APP_TITLE}*")
                    return "\n".join(report_lines)

                # 리포트 생성
                markdown_report = generate_search_report(query, results)

                # 옵시디언으로 내보내기 함수
                def save_to_obsidian(content: str, filename: str) -> tuple:
                    """옵시디언 Vault에 마크다운 파일 저장"""
                    # 경로 확인 (사이드바 버튼과 동일한 방식)
                    vault_path_str = ""
                    
                    # 1. 세션 스테이트 (설정 페이지에서 입력 중인 값)
                    if st.session_state.get("obsidian_vault_input"):
                        vault_path_str = st.session_state.get("obsidian_vault_input", "").strip()
                    
                    # 2. 세션 스테이트의 저장된 설정
                    if not vault_path_str and st.session_state.get("current_settings"):
                        vault_path_str = st.session_state.current_settings.get("OBSIDIAN_VAULT", "").strip()
                    
                    # 3. .env 파일 직접 읽기
                    if not vault_path_str and ENV_FILE.exists():
                        with open(ENV_FILE, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip().startswith("OBSIDIAN_VAULT="):
                                    vault_path_str = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                                    break
                    
                    if not vault_path_str:
                        return False, "Obsidian Vault 경로가 설정되지 않았습니다."

                    vault_path = Path(vault_path_str)
                    if not vault_path.exists():
                        return False, f"Vault 경로가 존재하지 않습니다: {vault_path}"

                    # 파일명 정리 (특수문자 제거)
                    safe_filename = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)
                    file_path = vault_path / f"{safe_filename}.md"

                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        return True, str(file_path)
                    except Exception as e:
                        return False, str(e)

                # 다운로드/옵시디언/AI 리포트 버튼
                export_col1, export_col2, export_col3 = st.columns([1, 1, 1])
                with export_col1:
                    st.download_button(
                        label="📥 다운로드",
                        data=markdown_report,
                        file_name=f"search_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md",
                        mime="text/markdown",
                        key="download_report"
                    )
                with export_col2:
                    if st.button("🟣 옵시디언", key="obsidian_report"):
                        filename = f"검색_{query}_{datetime.now().strftime('%Y%m%d_%H%M')}"
                        success, result = save_to_obsidian(markdown_report, filename)
                        if success:
                            st.success(f"✅ 저장됨: {Path(result).name}")
                        else:
                            st.error(f"❌ {result}")
                with export_col3:
                    # API 설정 확인
                    provider, model_name, api_key = get_active_api_config()
                    if provider and api_key:
                        if st.button("🤖 AI 분석", key="ai_report"):
                            st.session_state["generate_ai_report"] = True
                    else:
                        if st.button("🤖 AI 분석", key="ai_report_disabled", disabled=True):
                            pass
                        st.caption("⚠️ 설정에서 API 키 등록 필요")

                # AI 리포트 생성
                if st.session_state.get("generate_ai_report"):
                    provider, model_name, api_key = get_active_api_config()
                    if provider and api_key:
                        with st.spinner(f"🤖 AI 분석 중... ({model_name})"):
                            # 검색 결과를 컨텍스트로 변환
                            context_parts = []
                            for i, doc in enumerate(results['documents'][0]):
                                meta = results['metadatas'][0][i]
                                source = meta.get('source', 'Unknown')
                                raw_page = meta.get('page', meta.get('page_number', '?'))
                                try:
                                    page_num = int(raw_page) + PAGE_OFFSET if str(raw_page).isdigit() else raw_page
                                except:
                                    page_num = raw_page
                                context_parts.append(f"[출처: {source}, p.{page_num}]\n{doc}")

                            context = "\n\n---\n\n".join(context_parts)

                            # AI 리포트 생성
                            ai_report = generate_ai_report(query, context, provider, model_name, api_key)

                        st.session_state["ai_report_content"] = ai_report
                        st.session_state["generate_ai_report"] = False
                        st.rerun()

                # AI 리포트 표시
                if st.session_state.get("ai_report_content"):
                    st.markdown("---")
                    st.markdown("### 🤖 AI 분석 리포트")
                    st.markdown(st.session_state["ai_report_content"])

                    # AI 리포트 내보내기 버튼
                    ai_col1, ai_col2, ai_col3 = st.columns([1, 1, 1])
                    with ai_col1:
                        st.download_button(
                            label="📥 AI 리포트 다운로드",
                            data=st.session_state["ai_report_content"],
                            file_name=f"ai_report_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md",
                            mime="text/markdown",
                            key="download_ai_report"
                        )
                    with ai_col2:
                        if st.button("🟣 옵시디언 저장", key="obsidian_ai_report"):
                            filename = f"AI분석_{query}_{datetime.now().strftime('%Y%m%d_%H%M')}"
                            # 함수 내부에서 자동으로 경로를 가져옴
                            success, result = save_to_obsidian(st.session_state["ai_report_content"], filename)
                            if success:
                                st.success(f"✅ 저장됨: {Path(result).name}")
                            else:
                                st.error(f"❌ {result}")
                    with ai_col3:
                        if st.button("🗑️ 닫기", key="close_ai_report"):
                            st.session_state["ai_report_content"] = None
                            st.rerun()

                    st.markdown("---")

                st.markdown("---")

                # 개별 결과 표시
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]

                    # 출처 정보
                    source = meta.get('source', 'Unknown')
                    raw_page = meta.get('page', meta.get('page_number', '?'))
                    page_num = raw_page
                    
                    lemma = meta.get('lemma', '')
                    category = meta.get('category', '')
                    author = meta.get('author', '')

                    # 하이라이팅 처리 (단순 텍스트 교체)
                    highlighted_doc = doc
                    if query:
                        # 한국어/영어/독일어 키워드 강조
                        keywords = query.split()
                        for kw in keywords:
                            if len(kw) > 1:
                                pattern = re.compile(re.escape(kw), re.IGNORECASE)
                                highlighted_doc = pattern.sub(f"<mark style='background-color: #FEF08A; border-radius: 2px; padding: 0 2px;'>{kw}</mark>", highlighted_doc)

                    # 카드 형식으로 표시
                    with st.expander(f"**[{i+1}] {source}** - p.{page_num} {f'| {lemma}' if lemma else ''}", expanded=(i==0)):
                        if category or author:
                            st.caption(f"📂 {category} {'| ✍️ ' + author if author else ''}")
                        st.markdown(highlighted_doc, unsafe_allow_html=True)
                        
                        # 추가 메타데이터 정보 (고급 사용자용)
                        if st.checkbox(f"메타데이터 보기 ##{i}", key=f"meta_{i}"):
                            st.json(meta)
            else:
                st.info("검색 결과가 없습니다.")

# ============================================================
# 파일 업로드 페이지
# ============================================================
# ============================================================
# 파일 업로드 페이지 (Cloud Edition - Disabled)
# ============================================================
# elif page == "📤 파일 업로드":
#     st.error("⛔️ 클라우드 버전에서는 파일 업로드를 Colab에서 수행합니다.")
#     st.info("Desktop/MS_Dev.nosync/Theology_AI_Lab_v4/01_Library/inbox 폴더에 파일을 넣고 Colab 인덱서를 실행하세요.")

# ============================================================
# 통계 페이지
# ============================================================
elif page == "📊 통계":
    st.markdown("""
        <div style="padding-bottom: 25px;">
            <h1 style="color: #2D3748; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 0;">📊 서재 현황</h1>
            <p style="color: #718096; font-size: 1.1em; font-weight: 400;">현재 인덱싱된 신학 자료들의 통계와 분포입니다.</p>
        </div>
    """, unsafe_allow_html=True)
    
    client, collection = load_db(str(DB_PATH))
    index_data = load_lemma_index(str(LEMMA_INDEX_PATH))

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "📄 인덱싱된 청크",
            f"{collection.count():,}개" if collection else "0개"
        )

    with col2:
        lemma_count = len(index_data.get("entries", {})) if index_data else 0
        st.metric("📖 표제어", f"{lemma_count:,}개")

    with col3:
        # 보관된 청킹 JSON 문서 수 (인덱싱 완료된 도서)
        archive_files = []
        if ARCHIVE_DIR.exists():
            archive_files = [f for f in ARCHIVE_DIR.glob("*.json") if not f.name.startswith("lemma_")]
        st.metric("📚 보관 문서", f"{len(archive_files)}권")

    st.markdown("---")

    # 소스별 분포 (ChromaDB에서 직접 조회)
    by_source = get_sources_from_db()

    if by_source:
        import pandas as pd

        total_chunks = sum(info.get("count", 0) for info in by_source.values())

        st.markdown(f"### 📚 인덱싱 소스 ({len(by_source)}개, 총 {total_chunks:,} 청크)")

        # 소스 유형 분류 (자동 추론)
        SOURCE_TYPES = {
            "TRE": "신학백과", "RGG": "신학백과", "EKL": "신학백과",
            "TDNT": "성서사전", "NIDNTT": "성서사전", "EDNT": "성서사전",
            "ThWAT": "성서사전", "EWNT": "성서사전",
            "HWPh": "철학사전",
            "KD": "교의학",
        }

        # 데이터 준비
        source_data = []
        for source, info in by_source.items():
            volumes = info.get("volumes", [])
            source_data.append({
                "소스": source,
                "유형": SOURCE_TYPES.get(source, "기타"),
                "권수": len(volumes) if volumes else 1,
                "청크": info.get("count", 0),
            })

        df = pd.DataFrame(source_data).sort_values("청크", ascending=False)

        # 필터 UI
        col1, col2 = st.columns([2, 1])
        with col1:
            search_source = st.text_input("소스 검색", placeholder="예: TRE, RGG...", key="source_search")
        with col2:
            all_types = ["전체"] + sorted(df["유형"].unique().tolist())
            selected_type = st.selectbox("유형 필터", all_types, key="type_filter")

        # 필터 적용
        filtered_df = df.copy()
        if search_source:
            filtered_df = filtered_df[filtered_df["소스"].str.contains(search_source, case=False)]
        if selected_type != "전체":
            filtered_df = filtered_df[filtered_df["유형"] == selected_type]

        # 테이블 표시 (상위 10개 + 더보기)
        show_all = st.checkbox(f"전체 표시 ({len(filtered_df)}개)", key="show_all_sources")
        display_df = filtered_df if show_all else filtered_df.head(10)

        st.dataframe(
            display_df,
            column_config={
                "소스": st.column_config.TextColumn("소스", width="medium"),
                "유형": st.column_config.TextColumn("유형", width="small"),
                "권수": st.column_config.NumberColumn("권수", format="%d"),
                "청크": st.column_config.NumberColumn("청크", format="%d"),
            },
            hide_index=True,
            width="stretch"
        )

        # 차트 (상위 10개만)
        if len(df) > 0:
            with st.expander("📊 청크 분포 차트", expanded=False):
                chart_df = df.head(10).set_index("소스")[["청크"]]
                st.bar_chart(chart_df)

        # ═══════════════════════════════════════════════════════════════════
        # 소스 관리 섹션
        # ═══════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("### 🔧 소스 관리")

        # 소스 선택
        source_list = sorted(by_source.keys())
        selected_source = st.selectbox(
            "관리할 소스 선택",
            ["선택하세요..."] + source_list,
            key="manage_source_select"
        )

        if selected_source and selected_source != "선택하세요...":
            source_info = by_source.get(selected_source, {})
            chunk_count = source_info.get("count", 0)

            col_info, col_actions = st.columns([2, 1])

            with col_info:
                st.info(f"**{selected_source}**: {chunk_count:,}개 청크")
                # 아카이브 파일 존재 여부 확인
                archive_file = ARCHIVE_DIR / f"{selected_source}.json"
                if archive_file.exists():
                    st.success(f"📦 아카이브 파일 존재: {archive_file.name}")
                else:
                    st.warning("⚠️ 아카이브 파일 없음 (재인덱싱 불가)")

            with col_actions:
                st.markdown("**작업 선택:**")

                # 삭제 버튼
                if st.button("🗑️ DB에서 삭제", key=f"delete_{selected_source}", type="secondary"):
                    st.session_state["confirm_delete"] = selected_source

                # 재인덱싱 버튼 (아카이브 파일 있을 때만)
                if archive_file.exists():
                    if st.button("🔄 재인덱싱", key=f"reindex_{selected_source}", type="primary"):
                        st.session_state["confirm_reindex"] = selected_source

            # 삭제 확인 다이얼로그
            if st.session_state.get("confirm_delete") == selected_source:
                st.warning(f"⚠️ **'{selected_source}'**의 {chunk_count:,}개 청크를 삭제하시겠습니까?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ 삭제 확인", key="confirm_delete_yes", type="primary"):
                        with st.spinner("삭제 중..."):
                            try:
                                deleted = delete_source_from_db(selected_source)
                                st.success(f"✅ '{selected_source}' 삭제 완료 ({deleted}개 청크)")
                                st.session_state["confirm_delete"] = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")
                with col_no:
                    if st.button("❌ 취소", key="confirm_delete_no"):
                        st.session_state["confirm_delete"] = None
                        st.rerun()

            # 재인덱싱 확인 다이얼로그
            if st.session_state.get("confirm_reindex") == selected_source:
                st.info(f"🔄 **'{selected_source}'** 재인덱싱: 기존 데이터 삭제 후 아카이브에서 다시 인덱싱합니다.")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ 재인덱싱 시작", key="confirm_reindex_yes", type="primary"):
                        with st.spinner("재인덱싱 중..."):
                            try:
                                result = reindex_source(selected_source)
                                st.success(f"✅ 재인덱싱 완료: {result}")
                                st.session_state["confirm_reindex"] = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"재인덱싱 실패: {e}")
                with col_no:
                    if st.button("❌ 취소", key="confirm_reindex_no"):
                        st.session_state["confirm_reindex"] = None
                        st.rerun()

    else:
        st.info("소스 정보가 없습니다.")

    # 경로 정보
    st.markdown("---")
    st.markdown("### 📂 데이터 저장소 경로 (Google Drive Cloud)")
    st.code(f"""
[Local Inbox] : {INBOX_DIR}
[Cloud Archive]: {ARCHIVE_DIR}
[Cloud DB]     : {DB_PATH}
""", language="text")

# ============================================================
# 설정 페이지
# ============================================================
elif page == "⚙️ 설정":
    st.markdown("""
        <div style="padding-bottom: 25px;">
            <h1 style="color: #2D3748; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 0;">⚙️ 서재 환경 설정</h1>
            <p style="color: #718096; font-size: 1.1em; font-weight: 400;">AI 모델, API 키, 그리고 옵시디언 볼트 경로를 관리합니다.</p>
        </div>
    """, unsafe_allow_html=True)

    # .env 파일 경로
    ENV_FILE = KIT_ROOT / ".env"

    # 현재 설정 로드 (전역 설정 기반)
    def load_env_settings():
        return load_global_settings()

    def save_env_settings(settings_to_save: dict):
        """설정을 .env 파일에 저장"""
        # 기존 내용 읽기
        existing_lines = []
        existing_keys = set()
        if ENV_FILE.exists():
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        key = stripped.split("=", 1)[0].strip()
                        if key in settings_to_save:
                            existing_keys.add(key)
                            existing_lines.append(f"{key}={settings_to_save[key]}\n")
                        else:
                            existing_lines.append(line)
                    else:
                        existing_lines.append(line)

        # 새 키 추가
        for key, value in settings_to_save.items():
            if key not in existing_keys:
                existing_lines.append(f"{key}={value}\n")

        # 저장
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(existing_lines)

    # 세션 상태 활용하여 입력값 유지
    if "settings_loaded" not in st.session_state:
        st.session_state.current_settings = load_env_settings()
        st.session_state.settings_loaded = True

    settings = st.session_state.current_settings

    # ─────────────────────────────────────────────────────────
    # 앱 타이틀 설정
    # ─────────────────────────────────────────────────────────
    st.markdown("### 📝 앱 타이틀 설정")
    st.caption("검색 페이지에 표시되는 타이틀을 수정할 수 있습니다.")

    app_title_input = st.text_input(
        "앱 타이틀",
        value=settings.get("APP_TITLE", "Theology AI Lab"),
        placeholder="예: My Digi-Th-Library",
        key="app_title_input"
    )

    st.markdown("---")

    # ─────────────────────────────────────────────────────────
    # 옵시디언 설정 (v2.3: 다중 볼트 이력 관리)
    # ─────────────────────────────────────────────────────────
    st.markdown("### 📝 Obsidian 연동 설정")
    st.caption("검색 결과를 Obsidian 노트로 저장할 수 있습니다.")

    VAULT_HISTORY_FILE = SCRIPT_DIR / "vault_history.json"
    
    def load_vault_history():
        if VAULT_HISTORY_FILE.exists():
            try:
                with open(VAULT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_vault_history(vault_path):
        history = load_vault_history()
        if vault_path in history:
            history.remove(vault_path)
        history.insert(0, vault_path)
        history = history[:5]  # 최근 5개만 유지
        with open(VAULT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    vault_history = load_vault_history()
    
    # 1. 최근 사용된 볼트 선택
    selected_vault_from_history = ""
    if vault_history:
        selected_vault_from_history = st.selectbox(
            "최근 사용된 Vault",
            options=["-- 직접 입력 --"] + vault_history,
            index=0
        )

    # 2. 볼트 경로 입력
    if selected_vault_from_history != "-- 직접 입력 --":
        default_vault = selected_vault_from_history
    else:
        default_vault = settings.get("OBSIDIAN_VAULT", "")
    
    obsidian_vault_input = st.text_input(
        "Obsidian Vault 경로",
        value=default_vault,
        placeholder="예: /Users/username/Documents/MyVault",
        key="obsidian_vault_input",
        help="Obsidian Vault의 전체 경로를 입력하세요"
    )

    # 경로가 변경/입력되면 이력에 추가
    if obsidian_vault_input and obsidian_vault_input != settings.get("OBSIDIAN_VAULT", ""):
        vault_path = Path(obsidian_vault_input)
        if vault_path.exists():
            save_vault_history(obsidian_vault_input)

    # 경로 존재 확인
    if obsidian_vault_input:
        vault_path = Path(obsidian_vault_input)
        if vault_path.exists():
            st.success(f"✅ Vault 확인됨: {vault_path.name}")
        else:
            st.warning("⚠️ 경로가 존재하지 않습니다")

    st.markdown("---")

    # ─────────────────────────────────────────────────────────
    # 데이터 관리 (DB 초기화) [v4.3 추가]
    # ─────────────────────────────────────────────────────────
    st.markdown("### 🗑️ 데이터 관리")
    st.caption(f"클라우드 벡터 데이터베이스({DB_PATH})를 초기화합니다.")
    st.warning("⚠️ 주의: Google Drive와 동기화된 DB가 즉시 삭제됩니다. 신중하게 진행하세요!")
    
    col_reset1, col_reset2 = st.columns([1, 2])
    with col_reset1:
        if st.button("🧨 DB 초기화 (Reset)", type="primary", use_container_width=True):
            try:
                import shutil
                
                # 1. ChromaDB 삭제 (아카이브는 보존)
                if DB_PATH.exists():
                    shutil.rmtree(DB_PATH)
                    st.toast("🧹 벡터 DB가 초기화되었습니다.", icon="🗑️")
                
                # 3. 폴더 재생성
                DB_PATH.mkdir(parents=True, exist_ok=True)
                
                # 4. 캐시 무효화 (통계 즉시 반영)
                st.cache_resource.clear()
                st.cache_data.clear()
                
                st.success("✅ 초기화 완료! 이제 다시 인덱싱할 수 있습니다. (아카이브 파일은 보존됨)")
                st.rerun() # 페이지 새로고침으로 통계 0 반영
                
            except Exception as e:
                st.error(f"❌ 초기화 실패: {e}")

    st.markdown("---")

    # ─────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────
    # 🚀 2. 구글 드라이브 클라우드 연결
    # ─────────────────────────────────────────────────────────
    st.markdown("### ☁️ 클라우드 연결 (필수)")
    st.caption("구글 드라이브가 설치된 경로를 연결해야 정상 작동합니다.")

    # 현재 설정된 경로가 유효한지 확인
    is_path_valid = INBOX_DIR.exists() and DB_PATH.exists()
    
    if is_path_valid:
        st.success(f"✅ 연결됨: `{INBOX_DIR.parent.parent}`")
    else:
        st.error("❌ 연결 안 됨: 경로 설정이 필요합니다.")
    
    with st.expander("📂 구글 드라이브 경로 설정 마법사", expanded=not is_path_valid):
        st.info("💡 구글 드라이브 내 `Theology_AI_LAB` 폴더의 전체 경로를 입력해주세요.")
        
        # 기본값: 현재 경로가 절대경로라면 표시
        current_root_str = str(INBOX_DIR.parent.parent) if str(INBOX_DIR).startswith("/") else ""
        
        cloud_root_input = st.text_input(
            "Theology_AI_LAB 폴더 경로 (전체 경로)",
            value=current_root_str,
            placeholder="/Users/사용자/Library/CloudStorage/GoogleDrive-메일/내 드라이브/Theology_AI_LAB",
            help="Finder에서 폴더를 선택하고 `⌥ Opt + ⌘ Cmd + C`를 누르면 경로가 복사됩니다."
        )
        
        if st.button("🔄 경로 확인 및 연결"):
            root_path = Path(cloud_root_input.strip().strip('"').strip("'"))
            
            # 검증: 필수 하위 폴더 존재 여부
            check_inbox = root_path / "01_Library/inbox"
            check_db = root_path / "02_Brain/vector_db"
            
            if check_inbox.exists() and check_db.exists():
                # .env 업데이트 로직
                try:
                    env_lines = []
                    if ENV_FILE.exists():
                        env_lines = ENV_FILE.read_text(encoding='utf-8').splitlines()
                    
                    new_lines = []
                    keys_updated = {"INBOX_DIR": False, "ARCHIVE_DIR": False, "DB_PATH": False}
                    
                    for line in env_lines:
                        if line.startswith("INBOX_DIR="):
                            new_lines.append(f"INBOX_DIR={check_inbox}")
                            keys_updated["INBOX_DIR"] = True
                        elif line.startswith("ARCHIVE_DIR="):
                            new_lines.append(f"ARCHIVE_DIR={root_path}/01_Library/archive")
                            keys_updated["ARCHIVE_DIR"] = True
                        elif line.startswith("DB_PATH=") or line.startswith("CHROMA_DB_DIR="): # 구버전 호환
                            new_lines.append(f"DB_PATH={check_db}")
                            keys_updated["DB_PATH"] = True
                        else:
                            new_lines.append(line)
                    
                    # 없는 키 추가
                    if not keys_updated["INBOX_DIR"]:
                        new_lines.append(f"INBOX_DIR={check_inbox}")
                    if not keys_updated["ARCHIVE_DIR"]:
                        new_lines.append(f"ARCHIVE_DIR={root_path}/01_Library/archive")
                    if not keys_updated["DB_PATH"]:
                        new_lines.append(f"DB_PATH={check_db}")
                        
                    ENV_FILE.write_text("\n".join(new_lines), encoding='utf-8')
                    
                    st.toast("✅ 경로가 성공적으로 저장되었습니다!", icon="🎉")
                    st.success("설정이 저장되었습니다. 적용을 위해 앱을 새로고침합니다.")
                    time.sleep(1)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"저장 중 오류 발생: {e}")
            else:
                st.warning("⚠️ 유효하지 않은 경로입니다.")
                if not check_inbox.exists():
                    st.markdown(f"- ❌ 찾을 수 없음: `{check_inbox}`")
                if not check_db.exists():
                    st.markdown(f"- ❌ 찾을 수 없음: `{check_db}`")
                st.caption("폴더 구조가 `Theology_AI_LAB/01_Library/inbox` 형태인지 확인해주세요.")

    st.markdown("---")

    # ─────────────────────────────────────────────────────────
    # 3. API 키 관리 (상시 노출, 간섭 방지)
    # ─────────────────────────────────────────────────────────
    st.markdown("### 🔑 API 키 관리")
    st.caption("사용할 AI 모델의 API 키를 설정합니다. [Anthropic](https://console.anthropic.com/) | [OpenAI](https://platform.openai.com/api-keys) | [Google Gemini](https://aistudio.google.com/app/apikey)")

    # 저장된 키 로드 (없으면 빈 문자열)
    saved_anthropic_key = settings.get("ANTHROPIC_API_KEY", "")
    saved_openai_key = settings.get("OPENAI_API_KEY", "")
    saved_google_key = settings.get("GOOGLE_API_KEY", "")

    col_api1, col_api2, col_api3 = st.columns(3)
    
    with col_api1:
        anthropic_key = st.text_input(
            "Anthropic API Key",
            value=saved_anthropic_key,
            type="password",
            placeholder="sk-ant-api03-...",
            key="anthropic_key_input",
            help="Claude 모델 사용 시 필요"
        )
    
    with col_api2:
        openai_key = st.text_input(
            "OpenAI API Key",
            value=saved_openai_key,
            type="password",
            placeholder="sk-proj-...",
            key="openai_key_input",
            help="GPT 모델 사용 시 필요"
        )

    with col_api3:
        google_key = st.text_input(
            "Google API Key",
            value=saved_google_key,
            type="password",
            placeholder="AIza...",
            key="google_key_input",
            help="Gemini 모델 사용 시 필요"
        )

    st.markdown("---")

    # ─────────────────────────────────────────────────────────
    # RAG 모델 설정 (선택된 프로바이더의 모델만 표시)
    # ─────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────
    # 4. AI 추론 엔진 설정 (RAG 모델 선택)
    # ─────────────────────────────────────────────────────────
    st.markdown("### 🤖 AI 추론 엔진 설정")
    st.caption("질문에 답변할 메인 AI 모델을 선택합니다. 위에서 입력한 API 키가 필요합니다.")

    # 프로바이더별 모델 정의
    MODELS_BY_PROVIDER = {
        "anthropic": {
            "Claude Opus 4.5 (최신)": "claude-opus-4-5-20251101",
            "Claude Sonnet 4": "claude-sonnet-4-20250514",
            "Claude Haiku 4.5 (빠름)": "claude-haiku-4-5",
            "Claude 3.5 Sonnet": "claude-3-5-sonnet-20241022",
        },
        "openai": {
            "GPT-5.2 (최신)": "gpt-5.2-2025-12-11",
            "GPT-5.1": "gpt-5.1-2025-11-13",
            "GPT-4.1": "gpt-4.1-2025-04-14",
            "GPT-4.1 Mini (저렴)": "gpt-4.1-mini-2025-04-14",
            "GPT-4o": "gpt-4o",
        },
        "google": {
            "Gemini 3 Pro (최신)": "gemini-3-pro-preview",
            "Gemini 3 Flash": "gemini-3-flash-preview",
            "Gemini 2.5 Pro": "gemini-2.5-pro",
            "Gemini 2.5 Flash (추천)": "gemini-2.5-flash",
            "Gemini 2.0 Flash": "gemini-2.0-flash",
        },
    }

    # 프로바이더 선택 (라디오 버튼)
    provider = st.radio(
        "사용할 AI 프로바이더",
        ["Anthropic (Claude)", "OpenAI (GPT)", "Google (Gemini)"],
        horizontal=True,
        key="api_provider_select"
    )

    # 프로바이더 매핑
    provider_map = {
        "Anthropic (Claude)": "anthropic",
        "OpenAI (GPT)": "openai",
        "Google (Gemini)": "google",
    }
    selected_provider = provider_map[provider]

    # 선택된 프로바이더의 모델만 표시
    model_options = MODELS_BY_PROVIDER[selected_provider]

    current_model = settings.get("RAG_MODEL", "gemini-2.5-pro")
    # 현재 모델이 선택된 프로바이더에 있는지 확인
    current_model_display = next(
        (k for k, v in model_options.items() if v == current_model),
        list(model_options.keys())[0]  # 없으면 첫 번째 모델
    )

    # 현재 모델이 리스트에 없으면 인덱스 0 사용
    try:
        model_index = list(model_options.keys()).index(current_model_display)
    except ValueError:
        model_index = 0

    selected_model_display = st.selectbox(
        f"{provider} 모델",
        list(model_options.keys()),
        index=model_index,
        key="rag_model_select"
    )
    selected_model = model_options[selected_model_display]

    max_tokens = st.slider(
        "최대 응답 토큰",
        min_value=1024,
        max_value=8192,
        value=int(settings.get("RAG_MAX_TOKENS", 4096)),
        step=256,
        key="rag_max_tokens"
    )

    # ─────────────────────────────────────────────────────────
    # 저장 버튼
    # ─────────────────────────────────────────────────────────
    st.markdown("---")

    if st.button("💾 설정 저장 (Save All)", type="primary"):
        new_settings_data = {
            "ANTHROPIC_API_KEY": anthropic_key,
            "OPENAI_API_KEY": openai_key,
            "GOOGLE_API_KEY": google_key,
            "RAG_MODEL": selected_model,
            "RAG_MAX_TOKENS": str(max_tokens),
            "APP_TITLE": app_title_input,
            "OBSIDIAN_VAULT": obsidian_vault_input,
        }
        try:
            # .env 저장
            save_env_settings(new_settings_data)
            
            # 옵시디언 볼트 이력 저장
            if obsidian_vault_input:
                save_vault_history(obsidian_vault_input)
            
            # 세션 상태 업데이트
            st.session_state.current_settings = new_settings_data
            
            st.success("✅ 모든 설정이 안전하게 저장되었습니다.")
            st.rerun()  # 즉시 반영을 위해 재실행
            
        except Exception as e:
            st.error(f"❌ 저장 실패: {e}")

    # ─────────────────────────────────────────────────────────
    # 사용 가이드
    # ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📖 사용 가이드")

    GUI_GUIDE_PATH = KIT_ROOT / "docs" / "GUI_GUIDE.md"
    
    if GUI_GUIDE_PATH.exists():
        with st.expander("Cloud Edition 사용 설명서 보기", expanded=False):
            guide_content = GUI_GUIDE_PATH.read_text(encoding="utf-8")
            st.markdown(guide_content)
    
    # ─────────────────────────────────────────────────────────
    # Claude Desktop 연동 (간략화)
    # ─────────────────────────────────────────────────────────
    with st.expander("🔗 Claude Desktop 연동 정보", expanded=False):
        st.markdown("""
        **MCP 서버 설정 (claude_desktop_config.json)**
        
        이 설정을 추가하면 Claude Desktop 앱에서 내 서재를 직접 검색할 수 있습니다.
        """)
        st.code(f'''{{
  "mcpServers": {{
    "theology-lab": {{
      "command": "python",
      "args": ["{str(KIT_ROOT / "03_System/server.py")}"],
      "env": {{
        "ANTHROPIC_API_KEY": "your-api-key"
      }}
    }}
  }}
}}''', language="json")

    # 현재 상태 표시
    st.markdown("---")
    st.markdown("### 📊 현재 상태")

    col1, col2, col3 = st.columns(3)
    with col1:
        if settings.get("ANTHROPIC_API_KEY"):
            st.success("✅ Anthropic")
        else:
            st.warning("⚠️ Anthropic 미설정")

    with col2:
        if settings.get("OPENAI_API_KEY"):
            st.success("✅ OpenAI")
        else:
            st.info("ℹ️ OpenAI 미설정")

    with col3:
        if settings.get("GOOGLE_API_KEY"):
            st.success("✅ Google")
        else:
            st.info("ℹ️ Google 미설정")
