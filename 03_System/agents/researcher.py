import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from sentence_transformers import SentenceTransformer

class ResearcherAgent:
    """
    수석연구원 (Researcher)
    - ChromaDB 기반 의미 검색 (Semantic Search)
    - JSON Archive 기반 표제어 검색 (Lemma Search)
    - Dual-Search 프로토콜 통합 보고
    """
    
    def __init__(self, db_path: Optional[str] = None, archive_path: Optional[str] = None):
        self.name = "Researcher"
        
        # 경로 설정
        self.db_path = db_path or self._discover_db_path()
        self.archive_path = archive_path or self._discover_archive_path()
        
        # 모델 로딩 (Librarian과 공유 가능하도록 추후 최적화 고려)
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # ChromaDB 클라이언트 초기화
        self.collection = None
        self._init_chroma()

    def _discover_db_path(self):
        # 03_System/agents/researcher.py -> 03_System -> Theology_AI_Lab
        script_dir = Path(__file__).resolve().parent
        kit_root = script_dir.parent.parent
        
        # Priority 1: Check Env Var (Standard)
        if os.environ.get("CHROMA_DB_DIR"):
            return os.environ.get("CHROMA_DB_DIR")

        # Priority 2: Local Kit Structure
        local_db = kit_root / "02_Brain" / "vector_db"
        if local_db.exists():
            return str(local_db)
            
        # Fallback: Legacy (Keep for compatibility if needed, or remove)
        return "/Users/msn/Desktop/MS_Dev.nosync/data/Theology_Project.nosync/vector_db"

    def _discover_archive_path(self):
        script_dir = Path(__file__).resolve().parent
        kit_root = script_dir.parent.parent
        
        if os.environ.get("ARCHIVE_DIR"):
             return Path(os.environ.get("ARCHIVE_DIR"))

        local_archive = kit_root / "01_Library" / "archive"
        if local_archive.exists():
            return local_archive
            
        return Path("/Users/msn/Desktop/MS_Dev.nosync/data/Theology_Project.nosync/archive")

    def _init_chroma(self):
        if os.path.exists(self.db_path):
            try:
                client = chromadb.PersistentClient(path=self.db_path)
                self.collection = client.get_collection(name="theology_library")
                print(f"✅ [{self.name}] ChromaDB 연결 성공")
            except Exception as e:
                print(f"⚠️ [{self.name}] ChromaDB 연결 실패: {e}")

    def search_semantic(self, query: str, n_results: int = 5, source_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """ChromaDB 의미 검색"""
        if not self.collection:
            return []
            
        print(f"🔍 [{self.name}] 의미 검색 중: {query} (Source: {source_filter or 'All'})")
        query_vec = self.model.encode([query]).tolist()
        
        where_clause = {}
        if source_filter:
            # ChromaDB where filter
            where_clause = {"source": {"$contains": source_filter}} if "$" not in source_filter else {"source": source_filter}
            # Note: ChromaDB basic filtering. Assuming exact match or simpler logic.
            # Using simple exact match or $eq is safer if metadata is clean.
            # Let's try simple exact match logic first, or allow users to pass partial?
            # Creating a robust filter: if "RGG" is passed, we might want contains logic if keys are "RGG_Vol1".
            # However, Chroma current version might be strict.
            # safe assumption: use the filter dictionary directly if provided.
            where_clause = {"source": source_filter}

        # If source filter is partial (like "RGG"), but data is "RGG_Vol7", exact match fails.
        # But for now let's implement exact match or let the user handle it.
        # Upgrading simple implementation to accept where clause logic if complicated? 
        # No, let's keep it simple: Exact match on 'source' field often expected.
        # But wait, earlier rgg_rag.py analysis showed "source": "RGG_Vol7".
        # So "RGG" query won't match "RGG_Vol7" with simple {"source": "RGG"}.
        # We need processing.
        
        # NOTE: ChromaDB filter operators: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin
        # It does NOT verify substring ($contains) in standard release easily without special config or $like (some versions).
        # Let's do post-filtering if metadata is complex, or rely on $in if we can guess.
        # Actually, let's try WITHOUT the where clause first for broad fetch, OR use the logic from rgg_rag.py (fetch more, filter python side) 
        # to ensure we don't break on specific version limitations.
        # BUT efficiency matters. 
        # Better strategy: Fetch more results, then filter in Python if filter is requested.
        
        if source_filter:
             # Fetch more to allow for filtering
             n_results_fetch = n_results * 5
        else:
             n_results_fetch = n_results

        try:
            results = self.collection.query(
                query_embeddings=query_vec,
                n_results=n_results_fetch,
                # where=where_clause if source_filter else None # Skip DB-side filter to be safe against partial matches
            )
        except Exception as e:
            print(f"⚠️ Chroma Query Error: {e}")
            return []
        
        formatted = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                
                # Manual Filter Logic
                if source_filter:
                    src = meta.get("source", "")
                    if source_filter.upper() not in src.upper():
                        continue
                        
                formatted.append({
                    "text": doc,
                    "metadata": meta,
                    "type": "semantic"
                })
                if len(formatted) >= n_results:
                    break
                    
        return formatted

    def search_lemma(self, lemma: str, dict_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """JSON Archive 표제어 검색"""
        print(f"📖 [{self.name}] 표제어 검색 중: {lemma}")
        # ... (Legacy logic maintained, but not heavily used here)
        # Using dict_query tool might be better, but implementing basic fallback:
        results = []
        
        index_file = self.archive_path / "lemma_index.json"
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                index = json.load(f)
            
            query_norm = lemma.strip().lower()
            matches = index.get(query_norm, [])
            
            for match in matches:
                # Filter by dict_name if provided
                if dict_name:
                    if dict_name.lower() not in match["file"].lower():
                         continue

                results.append({
                    "lemma": lemma,
                    "source": match["file"],
                    "page": match.get("page", "?"),
                    "type": "lemma",
                    "file_path": str(self.archive_path / match["file"])
                })
        
        return results[:10]

    def dual_search(self, query: str, source: Optional[str] = None) -> Dict[str, Any]:
        """통합 검색 (Dual-Search Protocol)"""
        print(f"🚀 [{self.name}] Dual-Search 수행: {query} (Source: {source})")
        semantic_results = self.search_semantic(query, source_filter=source)
        lemma_results = self.search_lemma(query, dict_name=source)
        
        return {
            "query": query,
            "semantic": semantic_results,
            "lemma": lemma_results
        }

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="ARC Secretariat - Researcher Agent")
    parser.add_argument("--query", "-q", type=str, required=True, help="Unified Dual-Search Query")
    parser.add_argument("--source", "-s", type=str, help="Filter by Source (e.g., RGG, KD)")
    parser.add_argument("--semantic", action="store_true", help="Perform semantic search only")
    parser.add_argument("--lemma", action="store_true", help="Perform lemma search only")
    
    args = parser.parse_args()
    
    res = ResearcherAgent()
    
    if args.semantic and not args.lemma:
        results = {"semantic": res.search_semantic(args.query, source_filter=args.source)}
    elif args.lemma and not args.semantic:
        results = {"lemma": res.search_lemma(args.query, dict_name=args.source)}
    else:
        results = res.dual_search(args.query, source=args.source)
        
    print(json.dumps(results, ensure_ascii=False, indent=2))
