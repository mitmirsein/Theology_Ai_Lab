#!/usr/bin/env python3
"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  dict_query.py — Theological Dictionary JSON Archive Query Tool       ┃
┃                                                                       ┃
┃  Usage:                                                               ┃
┃    python dict_query.py --dict TRE --vol 1 --lemma "Aaron"            ┃
┃    python dict_query.py --dict RGG --vol 3 --page 150                 ┃
┃    python dict_query.py --dict HWPh --query "Substanz"                ┃
┃    python dict_query.py --list                                        ┃
┃                                                                       ┃
┃  Author: Theo-Tech ARC Pipeline                                       ┃
┃  Version: 1.0.0                                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Generator, Optional, Any

# ═══════════════════════════════════════════════════════════════════════════
# 📌 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

def discover_archive_path() -> Path:
    """아카이브 경로를 스마트하게 탐지: 상대 경로 -> 홈 디렉토리 순"""
    # 1. New Structure (theology-vector-db/tools/dict_query.py) -> data/Theology_Project.nosync/archive
    script_dir = Path(__file__).parent.absolute()
    # Go up: tools -> theology-vector-db -> projects -> MS_Dev.nosync -> data
    rel_path = script_dir.parent.parent.parent / "data" / "Theology_Project.nosync" / "archive"
    
    if rel_path.exists():
        return rel_path.resolve()
    
    # 2. Legacy fallback
    return Path.home() / "Desktop/MS_Dev.nosync/data/Theology_Project.nosync/archive"

ARCHIVE_PATH = discover_archive_path()
MAX_RESULTS = 50  # Maximum number of results to display
SNIPPET_LENGTH = 800  # Characters to show in text preview

# Known dictionary prefixes and their full names
DICT_NAMES = {
    "TRE": "Theologische Realenzyklopädie",
    "RGG": "Religion in Geschichte und Gegenwart",
    "EKL": "Evangelisches Kirchenlexikon",
    "HWPh": "Historisches Wörterbuch der Philosophie",
    "TDNT": "Theological Dictionary of the New Testament",
    "NIDNTT": "New International Dictionary of NT Theology",
    "LThK": "Lexikon für Theologie und Kirche",
}

INDEX_FILE = ARCHIVE_PATH / "lemma_index.json"

# ═══════════════════════════════════════════════════════════════════════════
# 📂 FILE DETECTION & LOADING
# ═══════════════════════════════════════════════════════════════════════════


def find_dict_file(dict_name: str, volume: Optional[int] = None) -> Optional[Path]:
    """
    Find the JSON file matching the dictionary name and optional volume.
    
    Handles patterns like:
      - TRE_Bd1.json, TRE_Bd01.json
      - RGG_Vol2.json, RGG_vol_2.json
      - EKL_Vol1.json
    """
    if not ARCHIVE_PATH.exists():
        print(f"❌ Archive path not found: {ARCHIVE_PATH}")
        print("   Please ensure the external drive is mounted.")
        return None
    
    # Build regex pattern
    if volume is not None:
        # Match variations: _Bd1, _Bd01, _Vol1, _vol_1, etc.
        patterns = [
            rf"{dict_name}[_-]?(?:Bd|Vol|vol|Band|band)[_-]?0?{volume}\.json$",
            rf"{dict_name}[_-]?{volume}\.json$",
        ]
    else:
        patterns = [rf"^{dict_name}.*\.json$"]
    
    matches = []
    for f in ARCHIVE_PATH.iterdir():
        if f.is_file() and f.suffix == ".json":
            for pattern in patterns:
                if re.match(pattern, f.name, re.IGNORECASE):
                    matches.append(f)
                    break
    
    if not matches:
        return None
    
    # Return first match (or could be more sophisticated)
    return sorted(matches)[0]


def list_available_dicts() -> dict[str, list[str]]:
    """Scan archive and list all available dictionaries and volumes."""
    if not ARCHIVE_PATH.exists():
        return {}
    
    result: dict[str, list[str]] = {}
    
    for f in sorted(ARCHIVE_PATH.iterdir()):
        if f.is_file() and f.suffix == ".json":
            # Try to extract dictionary name
            name = f.stem
            for prefix in DICT_NAMES.keys():
                if name.upper().startswith(prefix.upper()):
                    if prefix not in result:
                        result[prefix] = []
                    result[prefix].append(f.name)
                    break
            else:
                # Unknown dictionary
                if "OTHER" not in result:
                    result["OTHER"] = []
                result["OTHER"].append(f.name)
    
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 📖 JSON PARSING (Streaming & Standard)
# ═══════════════════════════════════════════════════════════════════════════


def stream_json_entries(file_path: Path) -> Generator[dict[str, Any], None, None]:
    """
    Stream JSON entries from a file. Handles multiple formats:
    - JSON Array: [{"entry": ...}, {"entry": ...}]
    - JSONL: {"entry": ...}\n{"entry": ...}
    - Single large object with entries list
    
    For very large files, uses ijson if available.
    """
    file_size = file_path.stat().st_size
    use_streaming = file_size > 50 * 1024 * 1024  # > 50MB
    
    if use_streaming:
        try:
            import ijson
            yield from _stream_with_ijson(file_path)
            return
        except ImportError:
            print("⚠️  Large file detected. Consider installing 'ijson' for better performance.")
    
    # Standard loading for smaller files or if ijson not available
    yield from _load_standard_json(file_path)


def _stream_with_ijson(file_path: Path) -> Generator[dict[str, Any], None, None]:
    """Stream using ijson for memory efficiency."""
    import ijson
    
    with open(file_path, "rb") as f:
        # Try to parse as array first
        try:
            parser = ijson.items(f, "item")
            for entry in parser:
                yield entry
            return
        except ijson.JSONError:
            f.seek(0)
        
        # Try as object with entries/items key
        for key in ["entries", "items", "data", "articles"]:
            try:
                f.seek(0)
                parser = ijson.items(f, f"{key}.item")
                for entry in parser:
                    yield entry
                return
            except (ijson.JSONError, StopIteration):
                continue


def _load_standard_json(file_path: Path) -> Generator[dict[str, Any], None, None]:
    """Standard JSON loading for smaller files."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    
    # Try JSONL format first (one object per line)
    if content.startswith("{") and "\n{" in content:
        for line in content.split("\n"):
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        return
    
    # Standard JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return
    
    # Handle different structures
    if isinstance(data, list):
        yield from data
    elif isinstance(data, dict):
        # Check for common container keys
        for key in ["entries", "items", "data", "articles", "content"]:
            if key in data and isinstance(data[key], list):
                yield from data[key]
                return
        # Single entry
        yield data


# ═══════════════════════════════════════════════════════════════════════════
# 🔍 SEARCH FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def get_entry_field(entry: dict, *keys: str, default: Any = None) -> Any:
    """Safely get a nested field from an entry."""
    for key in keys:
        # Try direct key
        if key in entry:
            return entry[key]
        # Try in metadata
        if "metadata" in entry and key in entry["metadata"]:
            return entry["metadata"][key]
    return default


def infer_lemma_from_text(entry: dict) -> str:
    """Try to infer lemma from the beginning of text."""
    text = get_entry_field(entry, "text", "content", "body", "Text", "article")
    if not text:
        return "?"
    
    # Take first line or first few words
    first_line = str(text).split('\n')[0].strip()
    
    # If first line is short (likely a title), use it
    if len(first_line) < 50:
        return first_line
    
    # Otherwise take first 3 words
    words = first_line.split()
    return " ".join(words[:3])


def search_by_lemma(
    file_path: Path, 
    query: str
) -> list[dict]:
    """Search entries by lemma/headword (case-insensitive)."""
    results = []
    query_lower = query.lower()
    
    for entry in stream_json_entries(file_path):
        lemma = get_entry_field(entry, "lemma", "headword", "title", "Lemma", "entry")
        if not lemma:
            lemma = infer_lemma_from_text(entry)
            
        if lemma and query_lower in str(lemma).lower():
            results.append(entry)
            if len(results) >= MAX_RESULTS:
                break
    
    return results


def search_by_page(
    file_path: Path, 
    page_number: int
) -> list[dict]:
    """Search entries by page number."""
    results = []
    
    for entry in stream_json_entries(file_path):
        page = get_entry_field(entry, "page_number", "page", "Page", "seite", "book_page")
        if page is not None:
            # Handle page ranges like "150-155"
            page_str = str(page)
            if "-" in page_str:
                try:
                    start, end = map(int, page_str.split("-"))
                    if start <= page_number <= end:
                        results.append(entry)
                except ValueError:
                    pass
            elif str(page_number) == page_str:
                results.append(entry)
            else:
                try:
                    if int(page) == page_number:
                        results.append(entry)
                except (ValueError, TypeError):
                    pass
        
        if len(results) >= MAX_RESULTS:
            break
    
    return results


def search_by_text(
    file_path: Path, 
    query: str
) -> list[dict]:
    """Free-text search within entry content."""
    results = []
    query_lower = query.lower()
    
    for entry in stream_json_entries(file_path):
        text = get_entry_field(entry, "text", "content", "body", "Text", "article")
        if text and query_lower in str(text).lower():
            results.append(entry)
            if len(results) >= MAX_RESULTS:
                break
    
    return results


def global_search_by_lemma(query: str) -> list[dict]:
    """Search for a lemma across all dictionaries using the index."""
    if not INDEX_FILE.exists():
        print("❌ Lemma index not found. Please run 'python build_lemma_index.py' first.")
        return []
    
    print("⏳ Loading index...")
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception as e:
        print(f"❌ Error loading index: {e}")
        return []
    
    query_norm = query.strip().lower()
    matches = index.get(query_norm, [])
    
    if not matches:
        return []
        
    results = []
    for match in matches:
        # Create lightweight entry for list view
        results.append({
            "lemma": query,
            "file": match["file"],
            "page_number": match.get("page", "?"),
            "dict_name": match["file"].replace(".json", ""),
            "_is_index_result": True
        })
    
    return results


def hydrate_entry(entry: dict) -> dict:
    """Fetch the full entry content from disk given an index result."""
    if not entry.get("_is_index_result"):
        return entry
        
    filename = entry["file"]
    file_path = ARCHIVE_PATH / filename
    target_page = entry.get("page_number")
    
    found = []
    if target_page and str(target_page) != "?":
         found = search_by_page(file_path, int(target_page) if isinstance(target_page, int) or str(target_page).isdigit() else target_page)
    else:
        found = search_by_lemma(file_path, entry["lemma"])
        
    if found:
        # Merge original metadata back for display purposes
        hydrated = found[0]
        hydrated["_is_index_result"] = True
        hydrated["file"] = filename
        return hydrated
    
    return entry


# ═══════════════════════════════════════════════════════════════════════════
# 📝 OUTPUT FORMATTING
# ═══════════════════════════════════════════════════════════════════════════


def format_entry_markdown(entry: dict, dict_name: str, highlight: Optional[str] = None) -> str:
    """Format a single entry as Markdown."""
    lemma = get_entry_field(entry, "lemma", "headword", "title", "Lemma", "entry")
    if not lemma or lemma == "Unknown":
        lemma = infer_lemma_from_text(entry)
        
    page = get_entry_field(entry, "page_number", "page", "Page", "seite", "book_page") or "?"
    text = get_entry_field(entry, "text", "content", "body", "Text", "article") or ""
    author = get_entry_field(entry, "author", "Author", "verfasser") or ""
    
    lines = []
    lines.append(f"## 📖 {lemma}")
    dict_source = dict_name
    if "_is_index_result" in entry:
        dict_source = entry.get("file", dict_name)
    lines.append(f"**Source:** {dict_source} | **Page:** {page}")
    if author:
        lines.append(f"**Author:** {author}")
    lines.append("")
    
    # Text snippet with optional highlighting
    if text:
        snippet = text[:SNIPPET_LENGTH]
        if len(text) > SNIPPET_LENGTH:
            snippet += "..."
        
        # Highlight query term if provided
        if highlight:
            pattern = re.compile(re.escape(highlight), re.IGNORECASE)
            snippet = pattern.sub(f"**{highlight}**", snippet)
        
        lines.append(f"> {snippet.replace(chr(10), chr(10) + '> ')}")
    
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def format_results_list(results: list[dict], dict_name: str) -> str:
    """Format multiple results as a selection list."""
    lines = []
    lines.append(f"\n## 🔍 Found {len(results)} result(s) in {dict_name}\n")
    
    for i, entry in enumerate(results, 1):
        lemma = get_entry_field(entry, "lemma", "headword", "title", "Lemma", "entry")
        if not lemma or lemma == "Unknown":
            lemma = infer_lemma_from_text(entry)
            
        page = get_entry_field(entry, "page_number", "page", "Page", "seite", "book_page") or "?"
        source = entry.get("file", dict_name) if "_is_index_result" in entry else dict_name
        lines.append(f"  [{i}] **{lemma}** (p. {page}) — {source}")
    
    lines.append("")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# 🚀 MAIN CLI
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Query theological dictionary JSON archives",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dict TRE --vol 1 --lemma "Aaron"
  %(prog)s --dict RGG --vol 3 --page 150
  %(prog)s --dict HWPh --query "Substanz"
  %(prog)s --list
        """
    )
    
    parser.add_argument("--list", action="store_true", 
                       help="List all available dictionaries")
    parser.add_argument("--dict", "-d", type=str, 
                       help="Dictionary name (TRE, RGG, EKL, HWPh, etc.)")
    parser.add_argument("--vol", "-v", type=int, 
                       help="Volume number")
    parser.add_argument("--lemma", "-l", type=str, 
                       help="Search by lemma/headword")
    parser.add_argument("--page", "-p", type=int, 
                       help="Search by page number")
    parser.add_argument("--query", "-q", type=str, 
                       help="Free-text search in content")
    parser.add_argument("--full", "-f", action="store_true",
                       help="Show full text instead of snippet")
    
    args = parser.parse_args()
    
    # List mode
    if args.list:
        print("\n" + "═" * 60)
        print("📚 Available Theological Dictionaries")
        print("═" * 60 + "\n")
        
        dicts = list_available_dicts()
        if not dicts:
            print("❌ No dictionaries found in archive.")
            print(f"   Path: {ARCHIVE_PATH}")
            sys.exit(1)
        
        for prefix, files in sorted(dicts.items()):
            full_name = DICT_NAMES.get(prefix, "Unknown")
            print(f"📖 **{prefix}** — {full_name}")
            for f in files:
                print(f"   └─ {f}")
            print()
        sys.exit(0)
    
    # Validate required args for search
    # if not args.dict:
    #     parser.error("--dict is required for search. Use --list to see available dictionaries.")
    
    if not any([args.lemma, args.page, args.query]):
        parser.error("At least one search mode is required: --lemma, --page, or --query")
    
    # Handle Global Search (No Dictionary Specified)
    if not args.dict:
        if args.lemma:
            print(f"\n🌍 Performing Global Search for: '{args.lemma}'")
            results = global_search_by_lemma(args.lemma)
            # Proceed to results display
            # We skip 'find_dict_file' loop
            file_path = Path("Global Index") # Dummy
            
        else:
             parser.error("--dict is required for --page or --query search types.")
    else:

        # Find the dictionary file
        file_path = find_dict_file(args.dict, args.vol)
        if not file_path:
            print(f"❌ Dictionary not found: {args.dict}" + (f" Vol.{args.vol}" if args.vol else ""))
            print("   Use --list to see available dictionaries.")
            sys.exit(1)
        
        print(f"\n📂 Searching: {file_path.name}")
        print("⏳ Processing...\n")
        
        # Perform search
        if args.lemma:
            results = search_by_lemma(file_path, args.lemma)
            highlight = args.lemma
        elif args.page:
            results = search_by_page(file_path, args.page)
        elif args.query:
            results = search_by_text(file_path, args.query)
            highlight = args.query
    
    # Output results
    highlight = args.lemma or args.query

    if not results:
        print("❌ No results found.")
        sys.exit(0)
    
    dict_display = f"{args.dict}" + (f" Vol.{args.vol}" if args.vol else "")
    
    if len(results) == 1:
        # Single result: show full entry
        entry = results[0]
        if entry.get("_is_index_result"):
             print(f"⏳ Fetching content from {entry['file']}...")
             entry = hydrate_entry(entry)
             
        if args.full:
            global SNIPPET_LENGTH
            SNIPPET_LENGTH = 999999
        print(format_entry_markdown(entry, dict_display, highlight))
    else:
        # Multiple results: show list first
        print(format_results_list(results, dict_display))
        
        # Ask user to select one
        try:
            choice = input("👉 Select entry number (or Enter to show all): ").strip()
            if choice:
                idx = int(choice) - 1
                if 0 <= idx < len(results):
                    selected = results[idx]
                    # Hydrate if it's an index result
                    if selected.get("_is_index_result"):
                        print(f"⏳ Fetching content from {selected['file']}...")
                        selected = hydrate_entry(selected)
                        
                    if args.full:
                        SNIPPET_LENGTH = 999999
                    print(format_entry_markdown(selected, dict_display, highlight))
                else:
                    print("⚠️  Invalid selection.")
            else:
                # Show all
                for entry in results:
                    print(format_entry_markdown(entry, dict_display, highlight))
        except (ValueError, EOFError):
            # Non-interactive mode: show all
            for entry in results:
                print(format_entry_markdown(entry, dict_display, highlight))


if __name__ == "__main__":
    main()
