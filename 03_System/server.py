#!/usr/bin/env python3
"""
신학 연구 MCP 서버 (v2 - 고급 메타데이터 지원)
- ChromaDB 벡터 검색 도구 제공
- Antigravity/Claude Desktop과 연동
- 표제어/권 정보 포함 학술 인용 형식 출력
"""

import os
from dotenv import load_dotenv

# Load .env explicitly from the kit root (parent of 03_System)
current_dir = os.path.dirname(os.path.abspath(__file__))
kit_root = os.path.dirname(current_dir) # Theology_AI_Lab
load_dotenv(os.path.join(kit_root, ".env"))

import chromadb
from mcp.server.fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

# =========================================================
# ⚙️ 설정 - 경로 탐지 (Env -> Relative -> Default)
def discover_db_path():
    """DB 경로탐지: .env 설정 우선, 없으면 02_Brain/vector_db"""
    # 1. Environment Variable (from .env)
    env_path = os.environ.get("CHROMA_DB_DIR")
    if env_path:
        # Handle relative config in .env (e.g., ./02_Brain/vector_db)
        if env_path.startswith("."):
            return os.path.abspath(os.path.join(kit_root, env_path))
        return env_path
        
    # 2. Default Relative Path (Theology AI Lab Standard)
    default_path = os.path.join(kit_root, "02_Brain", "vector_db")
    if os.path.exists(default_path):
        return default_path
        
    return default_path

DB_PATH = discover_db_path()
# =========================================================

# 로마 숫자 변환
ROMAN_NUMERALS = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 
                  6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X',
                  11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV'}

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

# MCP 서버 초기화
mcp = FastMCP("Theology-Research-Assistant")

# 전역 변수 (한 번만 로딩)
print("📡 서버 시작 중...")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
collection = None

# 🌐 원격 서버 접속 또는 로컬 파일 접속 선택
CHROMA_HOST = os.environ.get("CHROMA_HOST")

if CHROMA_HOST:
    print(f"🌐 원격 DB 서버에 접속 시도: {CHROMA_HOST}:8000")
    client = chromadb.HttpClient(host=CHROMA_HOST, port=8000)
    try:
        collection = client.get_collection(name="theology_library")
        print(f"✅ 원격 DB 연결 성공! (문서 수: {collection.count()}개)")
    except Exception as e:
        print(f"❌ 원격 접속 실패: {e}")
elif os.path.exists(DB_PATH):
    print(f"📂 로컬 DB 파일에 접속: {DB_PATH}")
    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        collection = client.get_collection(name="theology_library")
        print(f"✅ 로컬 DB 연결 성공! (문서 수: {collection.count()}개)")
    except Exception as e:
        print(f"⚠️ 컬렉션 없음: {e}")
else:
    print(f"⚠️ DB 경로를 찾을 수 없습니다. (환경변수 DB_PATH 또는 CHROMA_HOST 확인)")


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
        return "오류: 데이터베이스 연결 안 됨. 외장하드 연결 확인."

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
            
            chunk_text = (
                f"--- [출처 {i+1}: {citation}{lemma_info}] ---\n"
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
    archive_dir = os.path.join(kit_root, "01_Library", "archive")
    if not os.path.exists(archive_dir):
        return "보관된 문서가 없습니다."
        
    files = [f for f in os.listdir(archive_dir) if f.endswith('.json') and not f.startswith('lemma_')]
    if not files:
        return "보관된 문서가 없습니다."
        
    file_list = "\n".join([f"- {f.replace('.json', '')}" for f in files])
    return f"📚 서재 목록 ({len(files)}권):\n{file_list}"


import subprocess
import sys

# ... (existing imports)

# ... (existing code)

@mcp.tool()
def update_library() -> str:
    """
    서재(Archive) 업데이트 및 재색인.
    Inbox에 있는 새 파일을 처리하고 DB를 갱신합니다.
    
    Returns:
        작업 수행 결과 메시지
    """
    print("🚀 서재 업데이트 시작 (AI 요청)")
    
    # 실행할 스크립트 목록 (순서 중요)
    scripts = [
        # 1. PDF Processor
        [sys.executable, os.path.join(kit_root, "03_System", "utils", "local_pdf_processor.py"), os.path.join(kit_root, "01_Library", "inbox"), "-o", os.path.join(kit_root, "01_Library", "inbox")],
        # 2. DB Builder
        [sys.executable, os.path.join(kit_root, "03_System", "utils", "db_builder.py")],
        # 3. Lemma Indexer
        [sys.executable, os.path.join(kit_root, "03_System", "tools", "build_lemma_index.py")]
    ]
    
    results = []
    
    try:
        # 1. PDF Processing
        proc = subprocess.run(scripts[0], capture_output=True, text=True)
        if proc.returncode != 0:
            return f"❌ PDF 변환 실패:\n{proc.stderr}"
        results.append("✅ PDF 변환 완료")
        
        # 2. DB Building
        proc = subprocess.run(scripts[1], capture_output=True, text=True)
        if proc.returncode != 0:
            return f"❌ DB 색인 실패:\n{proc.stderr}"
        results.append("✅ DB 색인 완료")
        
        # 3. Lemma Indexing
        proc = subprocess.run(scripts[2], capture_output=True, text=True)
        if proc.returncode != 0:
            return f"❌ 인덱스 생성 실패:\n{proc.stderr}"
        results.append("✅ 인덱스 생성 완료")
        
        return "🎉 서재 업데이트가 완료되었습니다!\n" + "\n".join(results)
        
    except Exception as e:
        return f"❌ 시스템 오류: {str(e)}"

if __name__ == "__main__":
    mcp.run()
