#!/usr/bin/env python3
"""
신학 DB 검색 CLI (v3 - 통합 버전)
Usage: python search.py --query "검색어" [--source RGG] [--n 5]

Features:
- 권(Volume) 표시
- 표제어(Lemma) 표시  
- 학술 인용 형식 출력 (예: TDNT I, p.35)
- 소스 필터링 지원 (--source)
"""

import sys
import os
import argparse
import json
import chromadb
from sentence_transformers import SentenceTransformer

def discover_db_path():
    """DB 경로를 스마트하게 탐지"""
    env_path = os.environ.get("DB_PATH")
    if env_path:
        return env_path
    
    # 새로운 MS_Dev.nosync 구조
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rel_path = os.path.join(script_dir, "..", "..", "data", "Theology_Project.nosync", "vector_db")
    if os.path.exists(rel_path):
        return os.path.abspath(rel_path)
    
    # 레거시 경로
    return os.path.expanduser("~/Desktop/MS_Dev.nosync/data/Theology_Project.nosync/vector_db")

DB_PATH = discover_db_path()

ROMAN_NUMERALS = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 
                  6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X',
                  11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV'}

def format_citation(meta: dict) -> str:
    """학술 인용 형식으로 출력 정보 생성"""
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

def search(query: str, source: str = None, n_results: int = 5, output_json: bool = False):
    """통합 검색 함수"""
    
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    CHROMA_HOST = os.environ.get("CHROMA_HOST")
    if CHROMA_HOST:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=8000)
    else:
        client = chromadb.PersistentClient(path=DB_PATH)
    
    collection = client.get_collection(name="theology_library")
    query_vec = model.encode([query]).tolist()
    
    # 소스 필터링 시 더 많이 가져와서 후처리 (순위가 낮을 수 있으므로 대량 조회)
    fetch_n = n_results * 100 if source else n_results
    results = collection.query(query_embeddings=query_vec, n_results=fetch_n)
    
    output = []
    count = 0
    
    if results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            if meta is None:
                continue
            
            # 소스 필터링
            if source:
                source_val = meta.get('source', '')
                if source.lower() not in source_val.lower():
                    continue
            
            citation = format_citation(meta)
            lemma_info = ""
            if meta.get('lemma_chunk_index') and meta.get('lemma_total_chunks'):
                lemma_info = f" [{meta['lemma_chunk_index']}/{meta['lemma_total_chunks']}]"
            
            result_item = {
                "rank": count + 1,
                "citation": citation + lemma_info,
                "text": doc[:800] if len(doc) > 800 else doc,
                "metadata": meta
            }
            output.append(result_item)
            
            if not output_json:
                print(f"━━━ [{count+1}] {citation}{lemma_info} ━━━")
                print(doc[:500] + "..." if len(doc) > 500 else doc)
                print()
            
            count += 1
            if count >= n_results:
                break
    
    if output_json:
        print(json.dumps({"query": query, "source_filter": source, "results": output}, ensure_ascii=False, indent=2))
    elif count == 0:
        print(f"조건에 맞는 관련 내용을 찾을 수 없습니다.")
    
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="신학 DB 시맨틱 검색 CLI")
    parser.add_argument("-q", "--query", required=True, help="검색어")
    parser.add_argument("-s", "--source", help="소스 필터 (예: RGG, EKL, TDNT)")
    parser.add_argument("-n", "--num", type=int, default=5, help="결과 수 (기본: 5)")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")
    
    args = parser.parse_args()
    
    if not args.json:
        print(f"🔍 검색어: {args.query}")
        if args.source:
            print(f"📚 소스 필터: {args.source}")
        print()
    
    search(args.query, args.source, args.num, args.json)
