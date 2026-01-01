#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz

# Tokenizer equivalent
try:
    import tiktoken
    ENC = tiktoken.get_encoding("cl100k_base")
    def get_token_count(text): return len(ENC.encode(text))
except ImportError:
    def get_token_count(text): return len(text) // 4

def extract_lemma(text: str) -> Optional[str]:
    sample = text.strip()[:300]
    patterns = [
        r'^([A-ZÄÖÜ]{2,}(?:\s+[A-ZÄÖÜ]{2,})*)[\.,\s]', # UPPERCASE
        r'^([α-ωά-ώΑ-Ω]+)[\s,\.]',                     # Greek
        r'^([א-ת]+)[\s,\.]'                            # Hebrew
    ]
    for p in patterns:
        match = re.search(p, sample)
        if match: return match.group(1).strip()
    return None

def chunk_text(text: str, chunk_size=2800, overlap=560):
    """Simple paragraph-aware chunker"""
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        if len(current_chunk) + len(p) < chunk_size:
            current_chunk += p + "\n\n"
        else:
            if current_chunk: chunks.append(current_chunk.strip())
            current_chunk = p + "\n\n"
    if current_chunk: chunks.append(current_chunk.strip())
    return chunks

def process_searchable_pdf(input_file: str, output_dir: str, columnar_ratio: int = 2,
                           source: str = None, volume: int = None, 
                           output_name: str = None, page_offset: int = 0):
    """
    Process a searchable PDF and extract text chunks.
    
    Args:
        input_file: Path to PDF file
        output_dir: Output directory for JSON chunks
        columnar_ratio: Pages per PDF page (default=2 for 1:2 columnar mapping)
        source: Source name (e.g., 'RGG', 'ThWAT'). Auto-detected if None.
        volume: Volume number. Auto-detected if None.
        output_name: Custom output filename. Auto-generated if None.
        page_offset: PDF pages to skip before content starts (default=0)
    """
    file_path = Path(input_file)
    filename = file_path.name
    
    print(f"📖 Opening Searchable PDF: {filename}...")
    doc = fitz.open(file_path)
    total_pages = len(doc)
    print(f"   📄 Total PDF Pages: {total_pages}")
    if columnar_ratio > 1:
        print(f"   📐 Columnar Ratio: 1:{columnar_ratio} (PDF page → Book pages)")
    if page_offset > 0:
        print(f"   📄 Page Offset: {page_offset} (content starts at PDF page {page_offset + 1})")

    # Auto-detect source and volume if not provided
    if source is None:
        rgg_match = re.search(r'RGG[^\\d]*4[^\\d]*(\\d+)', filename, re.IGNORECASE)
        thwat_match = re.search(r'(ThWAT|Theologisches Wörterbuch)[^\\d]*Bd\\.?\\s*(\\d+)', filename, re.IGNORECASE)
        if rgg_match:
            source = "RGG"
            volume = int(rgg_match.group(1)) if volume is None else volume
        elif thwat_match:
            source = "ThWAT"
            volume = int(thwat_match.group(2)) if volume is None else volume
        else:
            source = "Unknown"
            all_digits = re.findall(r'\\d+', filename)
            volume = int(all_digits[0]) if all_digits and volume is None else volume
    
    all_chunks = []
    
    for i in range(total_pages):
        page_num = i + 1 # PDF page indexing (1-based)
        if page_num % 100 == 0:
            print(f"   Processing Page {page_num}/{total_pages}...")
            
        page = doc[i]
        text = page.get_text() or ""
        
        # If text is empty, try a more aggressive mode
        if not text.strip():
            text = page.get_text("text") # try explicit text mode
        
        unit_chunks = chunk_text(text)
        for j, chunk in enumerate(unit_chunks):
            lemma = extract_lemma(chunk)
            
            # Calculate book page from PDF page using columnar ratio and offset
            if columnar_ratio > 1:
                effective_page = max(1, page_num - page_offset)
                book_page_left = (effective_page * columnar_ratio) - (columnar_ratio - 1)
                book_page_right = effective_page * columnar_ratio
                book_page_str = f"{book_page_left}-{book_page_right}"
            else:
                book_page_str = str(page_num)
            
            all_chunks.append({
                "id": f"{source}_{volume}_{page_num}_{j}",
                "text": chunk,
                "metadata": {
                    "source": source,
                    "volume": volume,
                    "pdf_page": page_num,
                    "book_page": book_page_str,
                    "lemma": lemma or "",
                    "chunk_tokens": get_token_count(chunk),
                    "filename": filename
                }
            })

    # Determine output filename
    if output_name:
        out_name = output_name
    else:
        out_name = f"{source}_Vol{volume}.json" if volume else f"{source}.json"
    out_path = Path(output_dir) / out_name
    
    print(f"💾 Saving {len(all_chunks)} chunks to {out_path}...")
    with open(out_path, 'w', encoding='utf-8') as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    
    print("✅ Done!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        # Default for RGG 4,5
        BASE_PATH = os.path.expanduser("~/Desktop/MS_Dev.nosync/data/Theology_Project.nosync")
        CHUNK = os.path.join(BASE_PATH, "chunk")
        PDF_FILE = os.path.join(CHUNK, "RGG 4,5 L-M_OCR.pdf")
        process_searchable_pdf(PDF_FILE, CHUNK)
    else:
        process_searchable_pdf(sys.argv[1], sys.argv[2])
