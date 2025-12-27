#!/usr/bin/env python3
"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  build_lemma_index.py — Theological Dictionary Index Builder          ┃
┃                                                                       ┃
┃  Usage:                                                               ┃
┃    python build_lemma_index.py                                        ┃
┃    python build_lemma_index.py --force                                ┃
┃                                                                       ┃
┃  Author: Theo-Tech ARC Pipeline                                       ┃
┃  Version: 1.0.0                                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from collections import defaultdict
from typing import Any, Generator

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, desc=None, unit=None):
        print(f"Processing: {desc}")
        return iterable

# Import streaming logic from dict_query if available, otherwise define minimal version
try:
    from dict_query import stream_json_entries, get_entry_field
except ImportError:
    # Fallback if running standalone or import fails
    def stream_json_entries(file_path: Path) -> Generator[dict[str, Any], None, None]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        try:
            data = json.loads(content)
            if isinstance(data, list):
                yield from data
            elif isinstance(data, dict):
                for key in ["entries", "items", "data", "articles", "content"]:
                    if key in data and isinstance(data[key], list):
                        yield from data[key]
                        return
                yield data
        except json.JSONDecodeError:
            pass

    def get_entry_field(entry: dict, *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in entry:
                return entry[key]
            if "metadata" in entry and key in entry["metadata"]:
                return entry["metadata"][key]
        return default

# ═══════════════════════════════════════════════════════════════════════════
# 📌 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

def discover_archive_path() -> Path:
    """아카이브 경로를 스마트하게 탐지"""
    # tools/build_lemma_index.py -> ... -> data/Theology_Project.nosync/archive
    script_dir = Path(__file__).parent.absolute()
    rel_path = script_dir.parent.parent.parent / "data" / "Theology_Project.nosync" / "archive"
    if rel_path.exists():
        return rel_path.resolve()
        
    return Path.home() / "Desktop/MS_Brain.nosync/300 Tech/320 Coding/Projects.nosync/Theology_Project.nosync/archive"

ARCHIVE_PATH = discover_archive_path()
INDEX_FILE = ARCHIVE_PATH / "lemma_index.json"
META_FILE = ARCHIVE_PATH / "lemma_index_meta.json"

# ═══════════════════════════════════════════════════════════════════════════
# 🛠️ HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def normalize_lemma(lemma: str) -> str:
    """Normalize lemma for consistent indexing (lowercase, stripped)."""
    return lemma.strip().lower()

def load_json(path: Path, default: Any = None) -> Any:
    """Safely load JSON file."""
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"⚠️  Warning: Corrupt JSON file {path}, starting fresh.")
        return default

def save_json(path: Path, data: Any):
    """Save data to JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=None)  # Minimized for speed

# ═══════════════════════════════════════════════════════════════════════════
# 🚀 MAIN LOGIC
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Build/Update Theological Dictionary Lemma Index")
    parser.add_argument("--force", "-f", action="store_true", help="Force full rebuild")
    args = parser.parse_args()

    if not ARCHIVE_PATH.exists():
        print(f"❌ Archive path not found: {ARCHIVE_PATH}")
        sys.exit(1)

    print(f"📂 Scanning archive: {ARCHIVE_PATH}")

    # Load existing state
    index = {}
    metadata = {}
    
    if not args.force:
        index = load_json(INDEX_FILE, {})
        metadata = load_json(META_FILE, {})
        print(f"   Loaded existing index with {len(index)} lemmas.")
    else:
        print("   Force rebuild requested. Starting fresh.")

    # Scan current files
    current_files = {f.name: f for f in ARCHIVE_PATH.glob("*.json") 
                     if f.name not in ["lemma_index.json", "lemma_index_meta.json"]}
    
    # Identify changes
    new_or_modified = []
    deleted_files = set(metadata.keys()) - set(current_files.keys())
    
    for filename, filepath in current_files.items():
        mtime = filepath.stat().st_mtime
        if filename not in metadata or metadata[filename] != mtime:
            new_or_modified.append(filepath)
    
    # Early exit if nothing to do
    if not new_or_modified and not deleted_files and not args.force and index:
        print("✅ Index is up to date!")
        sys.exit(0)

    print(f"   Found {len(new_or_modified)} new/modified files and {len(deleted_files)} deleted files.")

    # 1. Handle Deletions: Remove entries pointing to deleted or modified files
    files_to_purge = deleted_files | {f.name for f in new_or_modified}
    
    if files_to_purge:
        print("🧹 Purging stale entries...")
        # We need to rebuild the index structure without the stale files
        # This is expensive but necessary for correctness. 
        # Structure: lemma -> list of {file, page, ...}
        for lemma in list(index.keys()):
            entries = index[lemma]
            # Filter out entries from stale files
            new_entries = [e for e in entries if e.get("file") not in files_to_purge]
            
            if new_entries:
                index[lemma] = new_entries
            else:
                del index[lemma]  # Remove lemma if no entries remain

        # Update metadata
        for f in files_to_purge:
            if f in metadata:
                del metadata[f]

    # 2. Process New/Modified Files
    if new_or_modified:
        print(f"📦 Indexing {len(new_or_modified)} files...")
        
        for file_path in tqdm(new_or_modified, unit="file"):
            filename = file_path.name
            file_entries = 0
            
            try:
                for entry in stream_json_entries(file_path):
                    raw_lemma = get_entry_field(entry, "lemma", "headword", "title", "Lemma", "entry")
                    page = get_entry_field(entry, "page_number", "page", "Page", "seite")
                    
                    if raw_lemma:
                        norm_lemma = normalize_lemma(str(raw_lemma))
                        
                        # Create index entry
                        idx_entry = {
                            "file": filename,
                            "page": page
                        }
                        
                        # Add dictionary name/volume if inferable (optional optimization)
                        # idx_entry["dict"] = ...
                        
                        if norm_lemma not in index:
                            index[norm_lemma] = []
                        index[norm_lemma].append(idx_entry)
                        file_entries += 1
                
                # Update metadata after successful processing
                metadata[filename] = file_path.stat().st_mtime
                
            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")

    # 3. Save Index
    print("💾 Saving index...")
    save_json(INDEX_FILE, index)
    save_json(META_FILE, metadata)
    
    print(f"✅ Done! Index contains {len(index)} distinct lemmas.")

if __name__ == "__main__":
    main()
