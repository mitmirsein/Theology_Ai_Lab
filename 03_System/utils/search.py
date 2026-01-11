#!/usr/bin/env python3
"""
신학 DB 검색 CLI (v4 - 하이브리드 검색)
Usage: python search.py --query "검색어" [--source RGG] [--n 5]

Features:
- 의미 검색 (Vector) + 키워드 검색 (BM25) 하이브리드
- 고전어 (히브리어/헬라어) 및 음역어 검색 지원
- 권(Volume) 및 표제어(Lemma) 표시
- 학술 인용 형식 출력 (예: TDNT I, p.35)
"""

import sys
import os
import argparse
import json
import glob
from pathlib import Path
from typing import List, Dict, Any, Tuple

import chromadb
from sentence_transformers import SentenceTransformer

# BM25 (optional, graceful fallback)
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False


def discover_paths() -> Tuple[str, str]:
    """DB 및 Archive 경로 탐지"""
    script_dir = Path(__file__).parent
    
    # Kit 구조 (배포용)
    kit_root = script_dir.parent.parent
    kit_db = kit_root / "02_Brain" / "vector_db"
    kit_archive = kit_root / "01_Library" / "archive"
    
    if kit_db.exists():
        return str(kit_db), str(kit_archive)
    
    # 개발 구조
    dev_db = os.path.expanduser("~/Desktop/MS_Dev.nosync/data/Theology_Project.nosync/vector_db")
    dev_archive = os.path.expanduser("~/Desktop/MS_Dev.nosync/data/Theology_Project.nosync/archive")
    
    return dev_db, dev_archive


DB_PATH, ARCHIVE_PATH = discover_paths()

ROMAN_NUMERALS = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 
                  6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X',
                  11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV'}


def format_citation(meta: dict) -> str:
    """학술 인용 형식으로 출력"""
    source = meta.get('source', 'Unknown')
    if '_Vol' in source:
        source = source.split('_Vol')[0]
    
    volume = meta.get('volume')
    page = meta.get('page_number', '?')
    lemma = meta.get('lemma')
    
    citation = source
    if volume and volume != "":
        vol_roman = ROMAN_NUMERALS.get(int(volume), str(volume)) if isinstance(volume, (int, str)) and str(volume).isdigit() else volume
        citation += f" {vol_roman}"
    if page and page != "N/A":
        citation += f", p.{page}"
    if lemma and lemma != "":
        citation += f" – {lemma}"
    return citation


def load_bm25_corpus() -> Tuple[List[str], List[Dict], 'BM25Okapi']:
    """Archive JSON에서 BM25 코퍼스 로드"""
    if not BM25_AVAILABLE:
        return [], [], None
    
    archive_path = Path(ARCHIVE_PATH)
    if not archive_path.exists():
        return [], [], None
    
    documents = []
    metadatas = []
    
    json_files = list(archive_path.glob("*.json"))
    for jf in json_files:
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for chunk in data:
                        text = chunk.get('text', chunk.get('content', ''))
                        if text:
                            documents.append(text)
                            metadatas.append(chunk.get('metadata', chunk))
        except Exception:
            continue
    
    if not documents:
        return [], [], None
    
    # 토큰화 (간단히 공백 분리)
    tokenized = [doc.lower().split() for doc in documents]
    bm25 = BM25Okapi(tokenized)
    
    return documents, metadatas, bm25


def bm25_search(query: str, bm25: 'BM25Okapi', documents: List[str], 
                metadatas: List[Dict], n_results: int = 10) -> List[Dict]:
    """BM25 키워드 검색"""
    if bm25 is None:
        return []
    
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)
    
    # 상위 결과 추출
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_results * 2]
    
    results = []
    for idx in top_indices:
        if scores[idx] > 0:  # 점수가 있는 것만
            results.append({
                "text": documents[idx],
                "metadata": metadatas[idx],
                "score": float(scores[idx]),
                "method": "bm25"
            })
    
    return results[:n_results]


def vector_search(query: str, model, collection, n_results: int = 10, 
                  source_filter: str = None) -> List[Dict]:
    """벡터 의미 검색"""
    query_vec = model.encode([query]).tolist()
    
    fetch_n = n_results * 10 if source_filter else n_results * 2
    results = collection.query(query_embeddings=query_vec, n_results=fetch_n)
    
    output = []
    if results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            if meta is None:
                continue
            
            # 소스 필터링
            if source_filter:
                source_val = meta.get('source', '')
                if source_filter.lower() not in source_val.lower():
                    continue
            
            output.append({
                "text": doc,
                "metadata": meta,
                "score": 1.0 - (i * 0.01),  # 순위 기반 점수
                "method": "vector"
            })
            
            if len(output) >= n_results:
                break
    
    return output


def hybrid_search(query: str, source: str = None, n_results: int = 5) -> List[Dict]:
    """하이브리드 검색 (TheologySearcher v4 사용)"""
    from pipeline.embedder import TheologyEmbedder
    from pipeline.searcher import TheologySearcher
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
    
    # 1. 컴포넌트 로드
    embedder = TheologyEmbedder()
    
    # Chroma DB 연결
    vector_db = Chroma(
        persist_directory=DB_PATH,
        embedding_function=lambda x: embedder.embed_documents(x),
        collection_name="theology_library"
    )
    
    searcher = TheologySearcher(vector_db)
    
    # 2. 하이브리드 인덱스 구축을 위해 전체 문서 로드 (CLI 환경이므로 실시간 구축)
    try:
        results = vector_db.get(include=["documents", "metadatas"])
        if results and results["documents"]:
            all_docs = [
                Document(page_content=d, metadata=m) 
                for d, m in zip(results["documents"], results["metadatas"])
            ]
            searcher.build_ensemble(all_docs, k=n_results)
    except Exception as e:
        print(f"⚠️ Hybrid Searcher 빌드 실패: {e}")
    
    # 3. 검색 실행
    raw_results = searcher.search(query)
    
    # 4. 소스 필터링 및 포맷 변환
    output = []
    for r in raw_results:
        meta = r.metadata
        if source and source.lower() not in meta.get('source', '').lower():
            continue
            
        output.append({
            "text": r.page_content,
            "metadata": meta,
            "score": 1.0,
            "method": "hybrid"
        })
        
        if len(output) >= n_results:
            break
            
    return output


def search(query: str, source: str = None, n_results: int = 5, output_json: bool = False):
    """통합 검색 함수 (하이브리드)"""
    
    results = hybrid_search(query, source, n_results)
    
    output = []
    for i, r in enumerate(results):
        meta = r.get('metadata', {})
        citation = format_citation(meta)
        method_tag = "🔤" if r.get('method') == 'bm25' else "🧠"
        
        lemma_info = ""
        if meta.get('lemma_chunk_index') and meta.get('lemma_total_chunks'):
            lemma_info = f" [{meta['lemma_chunk_index']}/{meta['lemma_total_chunks']}]"
        
        result_item = {
            "rank": i + 1,
            "citation": citation + lemma_info,
            "text": r['text'][:800] if len(r['text']) > 800 else r['text'],
            "metadata": meta,
            "method": r.get('method', 'unknown')
        }
        output.append(result_item)
        
        if not output_json:
            print(f"━━━ [{i+1}] {method_tag} {citation}{lemma_info} ━━━")
            print(r['text'][:500] + "..." if len(r['text']) > 500 else r['text'])
            print()
    
    if output_json:
        print(json.dumps({
            "query": query, 
            "source_filter": source, 
            "hybrid_mode": BM25_AVAILABLE,
            "results": output
        }, ensure_ascii=False, indent=2))
    elif not results:
        print(f"조건에 맞는 관련 내용을 찾을 수 없습니다.")
    
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="신학 DB 하이브리드 검색 CLI")
    parser.add_argument("-q", "--query", required=True, help="검색어 (한글, 독일어, 히브리어, 헬라어, 음역 가능)")
    parser.add_argument("-s", "--source", help="소스 필터 (예: RGG, EKL, TDNT)")
    parser.add_argument("-n", "--num", type=int, default=5, help="결과 수 (기본: 5)")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")
    
    args = parser.parse_args()
    
    if not args.json:
        print(f"🔍 검색어: {args.query}")
        if args.source:
            print(f"📚 소스 필터: {args.source}")
        print(f"🔄 검색 모드: {'하이브리드 (Vector + BM25)' if BM25_AVAILABLE else '벡터 전용'}")
        print()
    
    search(args.query, args.source, args.num, args.json)
