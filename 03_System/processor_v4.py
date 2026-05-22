#!/usr/bin/env python3
import os
import sys
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional

# OCR Support
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Add current dir to path to import pipeline package
SCRIPT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(SCRIPT_DIR))

from pipeline.embedder import TheologyEmbedder
from pipeline.semantic_chunker import SemanticChunker
from pipeline.router import ArchiveRouter
from langchain_chroma import Chroma
from langchain_core.documents import Document

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ProcessorV4")

class ProjectV4Processor:
    # OCR Languages for theological texts:
    # kor=Korean, deu=German, eng=English, grc=Ancient Greek, heb=Hebrew
    OCR_LANG = "kor+deu+eng+grc+heb"
    
    def __init__(self, db_dir: str):
        self.db_dir = db_dir
        self.embedder = TheologyEmbedder()
        self.chunker = SemanticChunker()
        self.router = ArchiveRouter()
        self.vector_db = None
        
    def _ocr_page(self, file_path: Path, page_num: int) -> Optional[str]:
        """Extract text from a scanned PDF page using OCR."""
        if not OCR_AVAILABLE:
            logger.warning("⚠️ OCR packages not installed. Skipping scanned page.")
            return None
            
        try:
            # Convert single page to image (page_num is 1-indexed for pdf2image)
            images = convert_from_path(
                str(file_path), 
                first_page=page_num, 
                last_page=page_num,
                dpi=300  # High DPI for better OCR accuracy
            )
            
            if not images:
                return None
                
            # Perform OCR
            text = pytesseract.image_to_string(images[0], lang=self.OCR_LANG)
            logger.info(f"🔍 OCR extracted {len(text)} chars from page {page_num}")
            return text.strip()
            
        except Exception as e:
            logger.error(f"OCR failed for page {page_num}: {e}")
            return None
        
    def _init_db(self):
        if self.vector_db is None:
            try:
                self.vector_db = Chroma(
                    persist_directory=self.db_dir,
                    embedding_function=self.embedder,  # Pass the object, not a lambda
                    collection_name="theology_library"
                )
            except Exception as e:
                logger.error(f"❌ DB Init Error: {e}. Attempting to proceed with fresh init if empty.")
                # If tenants table is missing, Chroma usually handles it on create, but if internal error persists,
                # we might need to rely on the client ensuring it exists.
                # For now, just logging.

    def process_file(self, file_path: Path) -> List[Document]:
        """Extracts text from PDF/EPUB/TXT and returns chunked documents."""
        logger.info(f"📄 Processing: {file_path.name}")
        
        # 1. Routing
        chunk_size, overlap, doc_type = ArchiveRouter.get_chunk_config(str(file_path))
        base_meta = ArchiveRouter.extract_theological_metadata(str(file_path))
        base_meta["doc_type"] = doc_type
        
        all_chunks = []
        
        # A. Handle Text Files
        if file_path.suffix.lower() == ".txt":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                
                if text.strip():
                    chunks = self.chunker.split_document(
                        text=text,
                        chunk_size=chunk_size,
                        chunk_overlap=overlap,
                        metadata_base=base_meta
                    )
                    all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"Failed to read TXT {file_path.name}: {e}")
                
        # B. Handle PDF/EPUB (PyMuPDF)
        else:
            try:
                doc = fitz.open(str(file_path))
                total_pages = len(doc)
                
                for i, page in enumerate(doc):
                    page_num = i + 1
                    text = page.get_text()
                    
                    # OCR fallback for scanned pages
                    if not text.strip():
                        logger.info(f"📷 Page {page_num} has no text layer. Attempting OCR...")
                        text = self._ocr_page(file_path, page_num) or ""
                    
                    if not text.strip():
                        continue
                    page_meta = base_meta.copy()
                    page_meta["page"] = page_num
                    
                    chunks = self.chunker.split_document(
                        text=text,
                        chunk_size=chunk_size,
                        chunk_overlap=overlap,
                        metadata_base=page_meta
                    )
                    all_chunks.extend(chunks)
                    
                    # Progress reporting for Streamlit
                    pct = int((i + 1) / total_pages * 100)
                    if pct % 20 == 0:
                        print(f"[PROGRESS] {pct}% | {file_path.name} (Page {page_num}/{total_pages})", flush=True)
                        
                doc.close()
            except Exception as e:
                 logger.error(f"Failed to read PDF/EPUB {file_path.name}: {e}")

        return all_chunks

    def index_files(self, inbox_dir: Path, archive_dir: Path):
        """Processes all files in inbox and moves them to archive."""
        # Use the generator version and consume all results
        for _ in self.index_files_with_progress(inbox_dir, archive_dir):
            pass
    
    def index_files_with_progress(self, inbox_dir: Path, archive_dir: Path, 
                                   metadata_overrides: Dict[str, Dict] = None):
        """
        Generator version: yields progress updates for Streamlit UI.
        
        Args:
            inbox_dir: Inbox directory
            archive_dir: Archive directory
            metadata_overrides: {filename: {author, title, ...}} 사용자 수정 메타데이터
            
        Yields:
            Dict with keys: status, file, progress, message, chunk_count
        """
        from pipeline.metadata_parser import MetadataParser
        
        files = []
        for ext in ["*.pdf", "*.epub", "*.txt"]:
            files.extend(list(inbox_dir.rglob(ext)))
        
        if not files:
            yield {"status": "done", "message": "No files found in inbox.", "total_files": 0}
            return

        self._init_db()
        total_files = len(files)
        parser = MetadataParser()
        metadata_overrides = metadata_overrides or {}
        
        session_stats = {
            "total_files": total_files,
            "processed_files": 0,
            "total_chunks": 0,
            "files_detail": []
        }
        
        for i, file_path in enumerate(files):
            file_name = file_path.name
            progress = int((i / total_files) * 100)
            
            yield {
                "status": "processing",
                "file": file_name,
                "progress": progress,
                "message": f"Processing {file_name}...",
                "file_index": i + 1,
                "total_files": total_files
            }
            
            try:
                # 1. 메타데이터 파싱 (자동 + 사용자 오버라이드)
                parsed = parser.parse(str(file_path))
                
                # [NEW] Sidecar JSON (.meta.json) 메타데이터 로드 (User-in-the-Loop)
                # 우선순위: book.meta.json > book.pdf.json > book.json
                sidecar_candidates = [
                    file_path.with_suffix(".meta.json"),
                    file_path.with_suffix(file_path.suffix + ".json"),
                    file_path.with_suffix(".json")
                ]
                
                sidecar_path = None
                for candidate in sidecar_candidates:
                    if candidate.exists():
                        sidecar_path = candidate
                        break
                
                if sidecar_path:
                    try:
                        logger.info(f"✨ Loading Sidecar Metadata: {sidecar_path.name}")
                        with open(sidecar_path, 'r', encoding='utf-8') as f:
                            sidecar_data = json.load(f)
                            # ParsedMetadata 필드 업데이트
                            for k, v in sidecar_data.items():
                                if hasattr(parsed, k):
                                    setattr(parsed, k, v)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to load sidecar JSON {sidecar_path.name}: {e}")

                # 사용자 오버라이드 적용 (Code Level)
                if file_name in metadata_overrides:
                    for key, val in metadata_overrides[file_name].items():
                        if hasattr(parsed, key):
                            setattr(parsed, key, val)
                
                # 2. 청킹 설정 적용
                chunk_size = parsed.chunk_size
                overlap = parsed.chunk_overlap
                
                # 3. 파일 처리 (기존 로직 재사용)
                chunks = self.process_file_with_metadata(file_path, parsed)
                
                if chunks:
                    # 4. DB 인덱싱 (배치 단위로 OOM 방지)
                    BATCH_SIZE = 100  # Optimized for Colab T4 (was 10 for MPS)
                    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
                    
                    for batch_idx in range(total_batches):
                        start = batch_idx * BATCH_SIZE
                        end = min(start + BATCH_SIZE, len(chunks))
                        batch = chunks[start:end]
                        
                        batch_progress = int((batch_idx + 1) / total_batches * 100)
                        yield {
                            "status": "indexing",
                            "file": file_name,
                            "progress": progress,
                            "message": f"Indexing batch {batch_idx+1}/{total_batches} ({batch_progress}%)...",
                            "chunk_count": len(batch)
                        }
                        
                        self.vector_db.add_documents(batch)
                    
                    # 5. JSON 아카이브 저장
                    source_name = file_path.stem
                    json_archive_path = archive_dir / f"{source_name}.json"
                    os.makedirs(archive_dir, exist_ok=True)
                    
                    chunk_data = {
                        "source": file_path.name,
                        "metadata": parsed.to_dict(),
                        "indexed_at": datetime.now().isoformat(),
                        "total_chunks": len(chunks),
                        "chunks": [
                            {
                                "content": chunk.page_content,
                                "metadata": chunk.metadata
                            }
                            for chunk in chunks
                        ]
                    }
                    
                    with open(json_archive_path, "w", encoding="utf-8") as f:
                        json.dump(chunk_data, f, ensure_ascii=False, indent=2)
                    
                    # 6. Sidecar JSON 이동 (존재 시)
                    if sidecar_path and sidecar_path.exists():
                        try:
                            # Archive에도 .meta.json 형태로 저장
                            dest_sidecar = archive_dir / f"{source_name}.meta.json"
                            shutil.move(str(sidecar_path), str(dest_sidecar))
                            logger.info(f"🚚 Moved sidecar to {dest_sidecar.name}")
                        except Exception as e:
                            logger.warning(f"Failed to move sidecar: {e}")

                    # 7. Inbox에서 원본 삭제
                    file_path.unlink()
                    
                    session_stats["processed_files"] += 1
                    session_stats["total_chunks"] += len(chunks)
                    session_stats["files_detail"].append({
                        "name": file_name,
                        "chunks": len(chunks),
                        "doc_type": parsed.doc_type,
                        "author": parsed.author
                    })
                    
                    yield {
                        "status": "completed",
                        "file": file_name,
                        "progress": int(((i + 1) / total_files) * 100),
                        "message": f"✅ {file_name}: {len(chunks)} chunks indexed",
                        "chunk_count": len(chunks)
                    }
                else:
                    yield {
                        "status": "warning",
                        "file": file_name,
                        "progress": progress,
                        "message": f"⚠️ No text found in {file_name}"
                    }
                    
            except Exception as e:
                import traceback
                yield {
                    "status": "error",
                    "file": file_name,
                    "progress": progress,
                    "message": f"❌ {file_name}: {str(e)}",
                    "traceback": traceback.format_exc()
                }
        
        # 최종 요약
        yield {
            "status": "done",
            "progress": 100,
            "message": "All files processed.",
            "session_stats": session_stats
        }
    
    def process_file_with_metadata(self, file_path: Path, parsed_meta) -> List[Document]:
        """Process file with parsed metadata using Semantic Chunker."""
        logger.info(f"📄 Processing: {file_path.name} (Type: {parsed_meta.doc_type})")
        
        # Build base metadata
        base_meta = {
            "source": file_path.name,
            "author": parsed_meta.author,
            "title": parsed_meta.title,
            "doc_type": parsed_meta.doc_type,
            "year": parsed_meta.year if parsed_meta.year else 0,
            "languages": ",".join(parsed_meta.languages) if parsed_meta.languages else "en",
            "tags": ",".join(parsed_meta.tags) if parsed_meta.tags else "",
        }
        
        if parsed_meta.series:
            base_meta["series"] = parsed_meta.series
            base_meta["volume"] = parsed_meta.volume
        
        # 1. 문서 전체 텍스트 추출 (페이지별)
        pages_content = []
        
        # TXT 파일
        if file_path.suffix.lower() == ".txt":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                pages_content = [{"page": 1, "text": text}]
            except Exception as e:
                logger.error(f"Failed to read TXT {file_path.name}: {e}")
                return []
        
        # PDF/EPUB (PyMuPDF)
        else:
            try:
                doc = fitz.open(str(file_path))
                for i, page in enumerate(doc):
                    page_num = i + 1
                    text = page.get_text()
                    
                    # OCR fallback
                    if not text.strip():
                        text = self._ocr_page(file_path, page_num) or ""
                    
                    if text.strip():
                        pages_content.append({"page": page_num, "text": text})
                doc.close()
            except Exception as e:
                logger.error(f"Failed to read PDF/EPUB {file_path.name}: {e}")
                return []

        if not pages_content:
            return []

        # 2. 전체 텍스트 병합 (Semantic Chunking을 위해 문맥 유지)
        full_text = "\n\n".join([p["text"] for p in pages_content])
        
        if not full_text.strip():
            return []

        # 3. Semantic Chunking 실행
        # parsed_meta.chunk_size (예: 800) -> max_chunk_size
        chunks = self.chunker.chunk(
            text=full_text,
            doc_type=parsed_meta.doc_type,  # dictionary, dogmatics 등
            max_chunk_size=parsed_meta.chunk_size or 1000, 
            metadata_base=base_meta
        )
        
        # 4. Convert SemanticChunks to LangChain Documents
        documents = []
        for chunk in chunks:
            # 페이지 매핑 (단순 휴리스틱: 청크 시작 부분이 포함된 페이지 찾기)
            chunk_start_excerpt = chunk.content[:50].strip()
            page_num = 1
            
            if chunk_start_excerpt:
                for p in pages_content:
                   if chunk_start_excerpt in p["text"]:
                       page_num = p["page"]
                       break
            
            # 메타데이터 병합
            final_meta = chunk.metadata.copy()
            # Apply page offset (e.g., if offset is -14, physical page 15 becomes logical page 1)
            # Or if offset is defined as "Logical Page 1 starts at Physical Page X", 
            # usually offset = (1 - Physical_Page_Start).
            # Here implementation assumes Additive Offset. 
            final_meta["page"] = max(1, page_num + parsed_meta.page_offset)
            
            doc = Document(page_content=chunk.content, metadata=final_meta)
            documents.append(doc)
            
        logger.info(f"   -> Created {len(documents)} semantic chunks")
        return documents

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", default="./01_Library/inbox")
    parser.add_argument("--archive", default="./01_Library/archive")
    parser.add_argument("--db", default="./02_Brain/vector_db")
    args = parser.parse_args()
    
    proc = ProjectV4Processor(db_dir=args.db)
    
    # Use generator version with progress display
    for update in proc.index_files_with_progress(Path(args.inbox), Path(args.archive)):
        if update["status"] == "done":
            print(f"\n🎉 {update['message']}")
            if "session_stats" in update:
                stats = update["session_stats"]
                print(f"   Files: {stats['processed_files']}/{stats['total_files']}")
                print(f"   Total Chunks: {stats['total_chunks']}")
        else:
            print(f"[{update['progress']:3d}%] {update['message']}")

