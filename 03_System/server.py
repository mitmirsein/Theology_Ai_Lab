#!/usr/bin/env python3
"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  신학 연구 MCP 서버 (v2.0 - Docker 호환)                               ┃
┃                                                                       ┃
┃  Features:                                                            ┃
┃    - ChromaDB 벡터 검색                                               ┃
┃    - Docker/로컬 환경 자동 감지                                        ┃
┃    - 통합 파이프라인 지원 (OCR 포함)                                   ┃
┃    - Antigravity/Claude Desktop 연동                                  ┃
┃                                                                       ┃
┃  Version: 2.0.0                                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""

import os

# tokenizers fork 크래시 방지 (멀티스레드 환경에서 subprocess 호출 시 충돌 방지)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import sys
import subprocess
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# 환경 설정
# ═══════════════════════════════════════════════════════════════════

def discover_kit_root() -> Path:
    """프로젝트 루트 경로 탐지 (Docker / 로컬 환경 지원)"""
    # Docker 환경
    if Path("/app/01_Library").exists():
        return Path("/app")

    # 로컬 환경: server.py -> 03_System -> Theology_AI_Lab
    current_dir = Path(__file__).parent.absolute()
    local_root = current_dir.parent

    if (local_root / "01_Library").exists():
        return local_root

    # Fallback
    return current_dir.parent


KIT_ROOT = discover_kit_root()

# .env 로드 (로컬 환경에서만 필요)
try:
    from dotenv import load_dotenv
    env_file = KIT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # Docker 환경에서는 환경변수로 직접 전달


def discover_db_path() -> str:
    """ChromaDB 경로 탐지"""
    # 1. 환경 변수
    env_path = os.environ.get("CHROMA_DB_DIR")
    if env_path:
        if env_path.startswith("."):
            return str(KIT_ROOT / env_path)
        return env_path

    # 2. Docker 경로
    docker_path = Path("/app/vector_db")
    if docker_path.exists():
        return str(docker_path)

    # 3. 로컬 기본 경로
    local_path = KIT_ROOT / "02_Brain" / "vector_db"
    return str(local_path)


def discover_archive_path() -> str:
    """Archive 경로 탐지"""
    env_path = os.environ.get("ARCHIVE_DIR")
    if env_path:
        if env_path.startswith("."):
            return str(KIT_ROOT / env_path)
        return env_path

    docker_path = Path("/app/01_Library/archive")
    if docker_path.exists():
        return str(docker_path)

    return str(KIT_ROOT / "01_Library" / "archive")


def discover_inbox_path() -> str:
    """Inbox 경로 탐지"""
    env_path = os.environ.get("INBOX_DIR")
    if env_path:
        if env_path.startswith("."):
            return str(KIT_ROOT / env_path)
        return env_path

    docker_path = Path("/app/01_Library/inbox")
    if docker_path.exists():
        return str(docker_path)

    return str(KIT_ROOT / "01_Library" / "inbox")


# 경로 설정
DB_PATH = discover_db_path()
ARCHIVE_PATH = discover_archive_path()
INBOX_PATH = discover_inbox_path()

# ═══════════════════════════════════════════════════════════════════
# 유틸리티
# ═══════════════════════════════════════════════════════════════════

ROMAN_NUMERALS = {
    1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V',
    6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X',
    11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV'
}


def format_citation(meta: dict) -> str:
    """학술 인용 형식으로 출력 정보 생성"""
    source = meta.get('source', 'Unknown')

    # source에서 _Vol 제거 (EKL_Vol1 → EKL)
    if '_Vol' in source:
        source = source.split('_Vol')[0]

    volume = meta.get('volume')
    page = meta.get('page_number', '?')
    lemma = meta.get('lemma')

    citation = source

    if volume and volume != "":
        try:
            vol_roman = ROMAN_NUMERALS.get(int(volume), str(volume))
        except (ValueError, TypeError):
            vol_roman = str(volume)
        citation += f" {vol_roman}"

    if page and page != "N/A":
        citation += f", p.{page}"

    if lemma and lemma != "":
        citation += f" – {lemma}"

    return citation


# ═══════════════════════════════════════════════════════════════════
# MCP 서버 초기화
# ═══════════════════════════════════════════════════════════════════

import chromadb
from mcp.server.fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

mcp = FastMCP("Theology-Research-Assistant")

# 전역 변수
print("=" * 50)
print("📡 Theology AI Lab MCP 서버 v2.0 시작")
print("=" * 50)
print(f"   📂 DB 경로: {DB_PATH}")
print(f"   📂 Archive: {ARCHIVE_PATH}")
print(f"   📂 Inbox: {INBOX_PATH}")

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
collection = None

# ChromaDB 연결
CHROMA_HOST = os.environ.get("CHROMA_HOST")

if CHROMA_HOST:
    port = int(os.environ.get("CHROMA_PORT", 8000))
    print(f"\n🌐 원격 DB 서버 접속: {CHROMA_HOST}:{port}")
    client = chromadb.HttpClient(host=CHROMA_HOST, port=port)
    try:
        collection = client.get_collection(name="theology_library")
        print(f"   ✅ 연결 성공! (문서 수: {collection.count()}개)")
    except Exception as e:
        print(f"   ❌ 연결 실패: {e}")
elif os.path.exists(DB_PATH):
    print(f"\n📂 로컬 DB 연결: {DB_PATH}")
    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        collection = client.get_collection(name="theology_library")
        print(f"   ✅ 연결 성공! (문서 수: {collection.count()}개)")
    except Exception as e:
        print(f"   ⚠️ 컬렉션 없음 (새로 생성됩니다): {e}")
else:
    print(f"\n⚠️ DB 경로 없음: {DB_PATH}")
    print("   CHROMA_DB_DIR 환경변수를 확인하세요.")

print("=" * 50)


# ═══════════════════════════════════════════════════════════════════
# MCP 도구들
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def search_theology_db(query: str, n_results: int = 5) -> str:
    """
    신학 연구 데이터베이스(EKL, RGG, TDNT 등)에서 의미 기반 검색.

    Args:
        query: 검색할 질문 또는 키워드
        n_results: 반환할 결과 수 (기본값: 5)

    Returns:
        관련 문서와 학술 인용 형식 출처 정보
    """
    if collection is None:
        return "오류: 데이터베이스 연결 안 됨. DB 경로를 확인하세요."

    print(f"🔍 검색: {query}")

    # 질문을 벡터로 변환
    query_vec = model.encode([query]).tolist()

    # 유사도 검색
    results = collection.query(
        query_embeddings=query_vec,
        n_results=n_results
    )

    # 결과 포맷팅
    response = []
    if results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            citation = format_citation(meta)

            # 청크 연속성 표시
            lemma_info = ""
            if meta.get('lemma_chunk_index') and meta.get('lemma_total_chunks'):
                lemma_info = f" [{meta['lemma_chunk_index']}/{meta['lemma_total_chunks']}]"

            # [v2.0] 카테고리 정보
            category_info = ""
            if meta.get('category'):
                cats = meta['category']
                if isinstance(cats, list):
                    category_info = f" ({', '.join(cats[:2])})"

            chunk_text = (
                f"--- [출처 {i+1}: {citation}{lemma_info}{category_info}] ---\n"
                f"{doc}\n"
            )
            response.append(chunk_text)

    if not response:
        return "관련 내용을 찾을 수 없습니다."

    return "\n".join(response)


@mcp.tool()
def get_db_stats() -> str:
    """
    데이터베이스 통계 확인.

    Returns:
        DB 상태 및 문서 수
    """
    if collection is None:
        return "DB 연결 안 됨"

    count = collection.count()
    return f"📚 Theology Library\n- 총 문서 수: {count}개\n- 경로: {DB_PATH}"


@mcp.tool()
def list_documents() -> str:
    """
    서재(Archive)에 있는 문서 목록 확인.

    Returns:
        보관된 문서 파일명 목록
    """
    if not os.path.exists(ARCHIVE_PATH):
        return "보관된 문서가 없습니다."

    files = [
        f for f in os.listdir(ARCHIVE_PATH)
        if f.endswith('.json') and not f.startswith('lemma_')
    ]

    if not files:
        return "보관된 문서가 없습니다."

    file_list = "\n".join([f"- {f.replace('.json', '')}" for f in sorted(files)])
    return f"📚 서재 목록 ({len(files)}권):\n{file_list}"


@mcp.tool()
def update_library() -> str:
    """
    서재(Archive) 업데이트 및 재색인.
    Inbox에 있는 새 파일을 처리하고 DB를 갱신합니다.
    (v2.0: OCR 자동 감지 및 통합 파이프라인 사용)

    Returns:
        작업 수행 결과 메시지
    """
    print("🚀 서재 업데이트 시작 (AI 요청)")

    # 통합 파이프라인 사용 (v2.0)
    pipeline_script = str(KIT_ROOT / "03_System" / "utils" / "pipeline.py")

    if os.path.exists(pipeline_script):
        # v2.0: 통합 파이프라인 사용
        try:
            result = subprocess.run(
                [sys.executable, pipeline_script],
                capture_output=True,
                text=True,
                timeout=600  # 10분 타임아웃
            )

            if result.returncode == 0:
                return "🎉 서재 업데이트 완료!\n\n" + result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            else:
                return f"❌ 업데이트 실패:\n{result.stderr}"

        except subprocess.TimeoutExpired:
            return "❌ 업데이트 시간 초과 (10분)"
        except Exception as e:
            return f"❌ 시스템 오류: {str(e)}"
    else:
        # Fallback: 기존 방식 (개별 스크립트 실행)
        scripts = [
            [sys.executable, str(KIT_ROOT / "03_System" / "utils" / "local_pdf_processor.py"),
             INBOX_PATH, "-o", INBOX_PATH],
            [sys.executable, str(KIT_ROOT / "03_System" / "utils" / "db_builder.py")],
            [sys.executable, str(KIT_ROOT / "03_System" / "tools" / "build_lemma_index.py")]
        ]

        results = []

        try:
            for i, script in enumerate(scripts):
                proc = subprocess.run(script, capture_output=True, text=True, timeout=300)
                if proc.returncode != 0:
                    return f"❌ 단계 {i+1} 실패:\n{proc.stderr}"
                results.append(f"✅ 단계 {i+1} 완료")

            return "🎉 서재 업데이트 완료!\n" + "\n".join(results)

        except subprocess.TimeoutExpired:
            return "❌ 작업 시간 초과"
        except Exception as e:
            return f"❌ 시스템 오류: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()
