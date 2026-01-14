import os
import re
from typing import List, Dict, Any
from transformers import AutoTokenizer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import logging

logger = logging.getLogger("Chunker")

class TheologyChunker:
    """
    Tokenizer-aware chunker for Theology AI Lab v4.
    Uses BGE-M3 tokenizer to ensure chunks fit model context perfectly.
    """
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        logger.info(f"📏 Initializing Tokenizer: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        
    def _token_length(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def split_document(self, 
                       text: str, 
                       chunk_size: int, 
                       chunk_overlap: int, 
                       metadata_base: Dict[str, Any]) -> List[Document]:
        """Splits a single page/string into chunks with high-fidelity metadata."""
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=self._token_length,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Split text into chunks
        raw_chunks = splitter.split_text(text)
        
        # Minimum chunk length filter (remove noise: page numbers, headers, etc.)
        MIN_CHUNK_LENGTH = 100
        raw_chunks = [c for c in raw_chunks if len(c) >= MIN_CHUNK_LENGTH]
        
        processed_chunks = []
        prev_offset = 0
        
        for i, chunk_text in enumerate(raw_chunks):
            # Robust Offset Calculation
            start_index = self._find_robust_offset(text, chunk_text, prev_offset)
            
            # Create LangChain Document
            metadata = metadata_base.copy()
            metadata["start_index"] = start_index
            metadata["chunk_index"] = i
            
            doc = Document(page_content=chunk_text, metadata=metadata)
            processed_chunks.append(doc)
            
            # Update prev_offset to help find next chunk sequentially (avoids duplicates issues)
            prev_offset = max(0, start_index + len(chunk_text) // 2) 

        return processed_chunks

    def _find_robust_offset(self, original: str, chunk: str, prev_offset: int) -> int:
        """Finds the text chunk within the original page using fallback strategies."""
        # 1. Direct Search from previous offset
        idx = original.find(chunk, prev_offset)
        if idx != -1:
            return idx
            
        # 2. Global search (if sequential fails)
        idx = original.find(chunk)
        if idx != -1:
            return idx
            
        # 3. Whitespace-insensitive search (Handle PDF extraction artifacts)
        norm_orig = " ".join(original.split())
        norm_chunk = " ".join(chunk.split())
        idx_norm = norm_orig.find(norm_chunk)
        
        if idx_norm != -1:
            # Approximate mapping back to original (not perfect but better than 0)
            return int((idx_norm / len(norm_orig)) * len(original))
            
        return 0

# Test Chunker
if __name__ == "__main__":
    chunker = TheologyChunker()
    test_page = "안녕하세요. 이것은 신학 연구를 위한 테스트 문장입니다. 바르트는 이렇게 말했습니다. '은혜란 공짜가 아니다.'"
    results = chunker.split_document(test_page, chunk_size=30, chunk_overlap=10, metadata_base={"page": 1})
    for c in results:
        print(f"[{c.metadata['start_index']}] {c.page_content}")
