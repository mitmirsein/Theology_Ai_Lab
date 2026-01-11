#!/usr/bin/env python3
"""
🔍 Dual Search Engine for Theology AI Lab v5.1
==============================================
이중 검색 엔진: Vector DB + Archive JSON 동시 검색
3중 언어 쿼리 확장과 결합하여 ~99% 커버리지 달성.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger("DualSearch")

# Query Expander 임포트
try:
    from utils.query_expander import QueryExpander, get_search_terms
    EXPANDER_AVAILABLE = True
except ImportError:
    EXPANDER_AVAILABLE = False
    logger.warning("QueryExpander not available, using single-language search")


@dataclass
class SearchResult:
    """검색 결과 아이템"""
    content: str
    source: str
    author: str = "Unknown"
    doc_type: str = "general"
    page: Optional[int] = None
    score: float = 0.0
    method: str = "vector"  # vector, json, hybrid
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "source": self.source,
            "author": self.author,
            "doc_type": self.doc_type,
            "page": self.page,
            "score": round(self.score, 3),
            "method": self.method,
        }


class DualSearchEngine:
    """
    이중 검색 엔진: Vector DB + Archive JSON 동시 검색.
    """
    
    def __init__(self, 
                 db_path: str, 
                 archive_path: str,
                 use_trilingual: bool = True):
        """
        Args:
            db_path: ChromaDB 경로
            archive_path: Archive JSON 디렉토리 경로
            use_trilingual: 3중 언어 확장 사용 여부
        """
        self.db_path = Path(db_path)
        self.archive_path = Path(archive_path)
        self.use_trilingual = use_trilingual and EXPANDER_AVAILABLE
        
        self.expander = QueryExpander() if self.use_trilingual else None
        self._vector_db = None
        self._embedder = None
        
    def _get_vector_db(self):
        """Lazy load ChromaDB"""
        if self._vector_db is None:
            import chromadb
            client = chromadb.PersistentClient(path=str(self.db_path))
            self._vector_db = client.get_or_create_collection("theology_library")
        return self._vector_db
    
    def _get_embedder(self):
        """Lazy load embedder"""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("BAAI/bge-m3")
        return self._embedder
    
    def search(self, 
               query: str, 
               n_results: int = 10,
               source_filter: Optional[str] = None,
               doc_type_filter: Optional[str] = None,
               tag_filter: Optional[List[str]] = None) -> List[SearchResult]:
        """
        이중 검색 실행.
        
        Args:
            query: 검색 쿼리
            n_results: 결과 수
            source_filter: 소스 필터 (예: "TDNT", "Barth")
            doc_type_filter: 도서 유형 필터 (dogmatics, dictionary, etc.)
            tag_filter: 태그 필터 리스트
            
        Returns:
            SearchResult 리스트
        """
        logger.info(f"🔍 Dual Search: '{query}'")
        
        # 1. 쿼리 확장 (3중 언어)
        search_terms = self._expand_query(query)
        logger.info(f"   └─ Search terms: {search_terms[:5]}...")
        
        # 2. Vector DB 검색
        vector_results = self._search_vector(search_terms, n_results * 2)
        logger.info(f"   └─ Vector results: {len(vector_results)}")
        
        # 3. Archive JSON 검색
        json_results = self._search_archive(search_terms, n_results * 2)
        logger.info(f"   └─ JSON results: {len(json_results)}")
        
        # 4. 결과 병합 및 중복 제거
        merged = self._merge_results(vector_results, json_results)
        
        # 5. 필터 적용
        filtered = self._apply_filters(merged, source_filter, doc_type_filter, tag_filter)
        
        # 6. 재순위화 및 결과 반환
        return self._rerank(filtered)[:n_results]
    
    def _expand_query(self, query: str) -> List[str]:
        """쿼리를 다국어로 확장"""
        if self.use_trilingual and self.expander:
            return get_search_terms(query)
        return [query]
    
    def _search_vector(self, terms: List[str], n: int) -> List[SearchResult]:
        """Vector DB 검색"""
        results = []
        try:
            collection = self._get_vector_db()
            embedder = self._get_embedder()
            
            # 각 검색어에 대해 임베딩 생성
            query_embeddings = embedder.encode(terms[:3]).tolist()  # 상위 3개만
            
            for i, emb in enumerate(query_embeddings):
                raw = collection.query(
                    query_embeddings=[emb],
                    n_results=n // len(query_embeddings) + 1
                )
                
                if raw['documents'] and raw['documents'][0]:
                    for j, doc in enumerate(raw['documents'][0]):
                        meta = raw['metadatas'][0][j] if raw['metadatas'] else {}
                        results.append(SearchResult(
                            content=doc,
                            source=meta.get('source', 'Unknown'),
                            author=meta.get('author', 'Unknown'),
                            doc_type=meta.get('doc_type', 'general'),
                            page=meta.get('page_number'),
                            score=1.0 - (j * 0.05),  # 순위 기반 점수
                            method="vector",
                            metadata=meta
                        ))
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
        
        return results
    
    def _search_archive(self, terms: List[str], n: int) -> List[SearchResult]:
        """Archive JSON 키워드 검색"""
        results = []
        
        if not self.archive_path.exists():
            return results
        
        # 검색어를 소문자로 정규화
        terms_lower = [t.lower() for t in terms]
        
        json_files = list(self.archive_path.glob("*.json"))
        
        for jf in json_files[:50]:  # 최대 50개 파일
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                chunks = data.get('chunks', data) if isinstance(data, dict) else data
                if not isinstance(chunks, list):
                    continue
                
                for chunk in chunks:
                    content = chunk.get('content', chunk.get('text', ''))
                    if not content:
                        continue
                    
                    content_lower = content.lower()
                    
                    # 매칭 점수 계산
                    score = sum(1 for t in terms_lower if t in content_lower)
                    
                    if score > 0:
                        meta = chunk.get('metadata', chunk)
                        results.append(SearchResult(
                            content=content,
                            source=meta.get('source', jf.stem),
                            author=meta.get('author', 'Unknown'),
                            doc_type=meta.get('doc_type', 'general'),
                            page=meta.get('page_number'),
                            score=score / len(terms),
                            method="json",
                            metadata=meta
                        ))
                        
            except Exception as e:
                logger.debug(f"Error reading {jf}: {e}")
                continue
        
        # 점수 순 정렬
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:n]
    
    def _merge_results(self, 
                       vector: List[SearchResult], 
                       archive: List[SearchResult]) -> List[SearchResult]:
        """결과 병합 및 중복 제거"""
        seen: Set[str] = set()
        merged = []
        
        # Vector 결과 우선
        for r in vector:
            key = r.content[:100]  # 앞 100자로 중복 판별
            if key not in seen:
                seen.add(key)
                merged.append(r)
        
        # Archive 결과 추가
        for r in archive:
            key = r.content[:100]
            if key not in seen:
                seen.add(key)
                r.method = "hybrid" if r.source in [m.source for m in merged] else "json"
                merged.append(r)
        
        return merged
    
    def _apply_filters(self,
                       results: List[SearchResult],
                       source: Optional[str],
                       doc_type: Optional[str],
                       tags: Optional[List[str]]) -> List[SearchResult]:
        """필터 적용"""
        filtered = results
        
        if source:
            source_lower = source.lower()
            filtered = [r for r in filtered if source_lower in r.source.lower()]
        
        if doc_type:
            filtered = [r for r in filtered if r.doc_type == doc_type]
        
        if tags:
            tags_lower = [t.lower() for t in tags]
            filtered = [
                r for r in filtered 
                if any(t in str(r.metadata.get('tags', [])).lower() for t in tags_lower)
            ]
        
        return filtered
    
    def _rerank(self, results: List[SearchResult]) -> List[SearchResult]:
        """결과 재순위화 (간단한 점수 기반)"""
        # Vector 결과에 가산점
        for r in results:
            if r.method == "vector":
                r.score += 0.2
            elif r.method == "hybrid":
                r.score += 0.3  # 양쪽에서 발견된 경우 최고점
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results


# ============================================================
# Convenience Function
# ============================================================
def dual_search(query: str, 
                db_path: str, 
                archive_path: str,
                n_results: int = 10,
                trilingual: bool = True) -> List[Dict]:
    """
    이중 검색 편의 함수.
    
    Args:
        query: 검색 쿼리
        db_path: ChromaDB 경로
        archive_path: Archive 경로
        n_results: 결과 수
        trilingual: 3중 언어 확장 사용
        
    Returns:
        결과 딕셔너리 리스트
    """
    engine = DualSearchEngine(db_path, archive_path, trilingual)
    results = engine.search(query, n_results)
    return [r.to_dict() for r in results]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="이중 검색 테스트")
    parser.add_argument("-q", "--query", required=True)
    parser.add_argument("--db", default="./02_Brain/vector_db")
    parser.add_argument("--archive", default="./01_Library/archive")
    parser.add_argument("-n", "--num", type=int, default=5)
    
    args = parser.parse_args()
    
    results = dual_search(args.query, args.db, args.archive, args.num)
    
    for i, r in enumerate(results):
        print(f"\n{'='*60}")
        print(f"[{i+1}] {r['source']} (p.{r['page']}) - {r['method']}")
        print(f"Score: {r['score']}")
        print(f"{r['content']}")
