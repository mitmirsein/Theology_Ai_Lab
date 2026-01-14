from typing import List, Any
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.documents import Document
import logging

logger = logging.getLogger("Searcher")

class TheologySearcher:
    """
    Hybrid Searcher combining Dense (Semantic) and Sparse (BM25) retrieval.
    Overcomes ChromaDB's single-vector limitation for BGE-M3.
    """
    def __init__(self, vector_db: Chroma):
        self.vector_db = vector_db
        self.retriever = None

    def build_ensemble(self, all_docs: List[Document], k: int = 8):
        """
        Initializes the Hybrid Retriever. 
        Requires all docs loaded initially for BM25 index.
        """
        logger.info(f"🚀 Building Ensemble Retriever (k={k})...")
        
        # 1. Semantic (Vector) Retriever
        vector_retriever = self.vector_db.as_retriever(
            search_kwargs={"k": k}
        )
        
        # 2. Lexical (BM25) Retriever
        bm25_retriever = BM25Retriever.from_documents(all_docs)
        bm25_retriever.k = k
        
        # 3. Combine with Weights (0.7 Semantic / 0.3 Keyword)
        # BGE-M3's dense is strong, but BM25 is great for specific 원어(Greek/Hebrew)
        self.retriever = EnsembleRetriever(
            retrievers=[vector_retriever, bm25_retriever],
            weights=[0.6, 0.4]
        )
        logger.info("✅ Hybrid Search Engine Ready.")

    def search(self, query: str) -> List[Document]:
        if self.retriever is None:
            # Fallback to pure vector search if ensemble not built
            logger.warning("⚠️ Ensemble not built. Falling back to simple vector search.")
            return self.vector_db.similarity_search(query, k=8)
            
        return self.retriever.invoke(query)
