#!/usr/bin/env python3
"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  build_lemma_index.py — Theological Dictionary Index Builder (v2.0)  ┃
┃                                                                       ┃
┃  Features:                                                            ┃
┃    - 확장된 메타데이터 인덱싱 (category, language, related)            ┃
┃    - by_category, by_source 보조 인덱스 생성                          ┃
┃    - 증분 업데이트 지원                                               ┃
┃                                                                       ┃
┃  Usage:                                                               ┃
┃    python build_lemma_index.py                                        ┃
┃    python build_lemma_index.py --force                                ┃
┃                                                                       ┃
┃  Version: 2.0.0                                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Any, Generator, List, Dict, Set

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, desc=None, unit=None):
        print(f"Processing: {desc}")
        return iterable


# ═══════════════════════════════════════════════════════════════════════════
# 📌 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

def discover_archive_path() -> Path:
    """아카이브 경로를 스마트하게 탐지"""
    script_dir = Path(__file__).parent.absolute()
    kit_root = script_dir.parent.parent

    # Priority 1: Env Var
    if os.environ.get("ARCHIVE_DIR"):
        return Path(os.environ.get("ARCHIVE_DIR"))

    # Priority 2: Docker 환경 (컨테이너 내)
    docker_path = Path("/app/01_Library/archive")
    if docker_path.exists():
        return docker_path

    # Priority 3: Standard Kit Path
    local_archive = kit_root / "01_Library" / "archive"
    if local_archive.exists():
        return local_archive.resolve()

    # Fallback
    return Path.home() / "Desktop/MS_Brain.nosync/300 Tech/320 Coding/Projects.nosync/Theology_Project.nosync/archive"


ARCHIVE_PATH = discover_archive_path()
INDEX_FILE = ARCHIVE_PATH / "lemma_index.json"
META_FILE = ARCHIVE_PATH / "lemma_index_meta.json"

# Index version for migration
INDEX_VERSION = "2.0"


# ═══════════════════════════════════════════════════════════════════════════
# 🛠️ HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def stream_json_entries(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """JSON 파일에서 엔트리를 스트리밍"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        data = json.loads(content)

        if isinstance(data, list):
            yield from data
        elif isinstance(data, dict):
            for key in ["entries", "items", "data", "articles", "content", "chunks"]:
                if key in data and isinstance(data[key], list):
                    yield from data[key]
                    return
            yield data
    except json.JSONDecodeError:
        pass


def get_entry_field(entry: dict, *keys: str, default: Any = None) -> Any:
    """엔트리에서 필드 값 추출 (metadata 내부도 검색)"""
    for key in keys:
        if key in entry:
            return entry[key]
        if "metadata" in entry and key in entry["metadata"]:
            return entry["metadata"][key]
    return default


def normalize_lemma(lemma: str) -> str:
    """Lemma 정규화 (소문자, 공백 정리)"""
    return lemma.strip().lower()


def load_json(path: Path, default: Any = None) -> Any:
    """JSON 파일 안전하게 로드"""
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"⚠️  Warning: Corrupt JSON file {path}, starting fresh.")
        return default


def save_json(path: Path, data: Any, indent: int = None):
    """JSON 파일 저장"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


# ═══════════════════════════════════════════════════════════════════════════
# 📊 INDEX BUILDER (v2.0)
# ═══════════════════════════════════════════════════════════════════════════

class EnhancedLemmaIndexer:
    """확장된 Lemma 인덱서 (v2.0)"""

    def __init__(self):
        # 메인 인덱스: lemma -> list of entries
        self.entries: Dict[str, List[Dict]] = defaultdict(list)

        # 보조 인덱스
        self.by_category: Dict[str, Set[str]] = defaultdict(set)
        self.by_source: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "volumes": set()}
        )

        # 파일 메타데이터 (mtime 추적)
        self.file_metadata: Dict[str, float] = {}

    def add_entry(
        self,
        lemma: str,
        file: str,
        page: Any,
        source: str = None,
        volume: Any = None,
        category: List[str] = None,
        language: str = None,
        related: List[str] = None,
    ):
        """인덱스에 엔트리 추가"""
        norm_lemma = normalize_lemma(lemma)

        # 메인 엔트리
        entry = {
            "file": file,
            "page": page,
        }

        # 선택적 필드 추가
        if source:
            entry["source"] = source
        if volume:
            entry["volume"] = volume
        if category:
            entry["category"] = category
        if language:
            entry["language"] = language
        if related:
            entry["related"] = related

        self.entries[norm_lemma].append(entry)

        # 보조 인덱스 업데이트
        if category:
            for cat in category:
                self.by_category[cat].add(norm_lemma)

        if source:
            self.by_source[source]["count"] += 1
            if volume:
                self.by_source[source]["volumes"].add(volume)

    def purge_file(self, filename: str):
        """특정 파일의 모든 엔트리 제거"""
        for lemma in list(self.entries.keys()):
            self.entries[lemma] = [
                e for e in self.entries[lemma] if e.get("file") != filename
            ]
            if not self.entries[lemma]:
                del self.entries[lemma]

    def rebuild_auxiliary_indices(self):
        """보조 인덱스 재구축"""
        self.by_category.clear()
        self.by_source.clear()

        for lemma, entries in self.entries.items():
            for entry in entries:
                # 카테고리 인덱스
                if "category" in entry:
                    for cat in entry["category"]:
                        self.by_category[cat].add(lemma)

                # 소스 인덱스
                source = entry.get("source")
                if source:
                    self.by_source[source]["count"] += 1
                    volume = entry.get("volume")
                    if volume:
                        self.by_source[source]["volumes"].add(volume)

    def to_dict(self) -> Dict[str, Any]:
        """직렬화 가능한 딕셔너리로 변환"""
        # Set을 List로 변환
        by_category_serializable = {
            cat: sorted(list(lemmas)) for cat, lemmas in self.by_category.items()
        }

        by_source_serializable = {}
        for source, data in self.by_source.items():
            by_source_serializable[source] = {
                "count": data["count"],
                "volumes": sorted(list(data["volumes"])),
            }

        return {
            "version": INDEX_VERSION,
            "updated_at": datetime.now().isoformat(),
            "entries": dict(self.entries),
            "by_category": by_category_serializable,
            "by_source": by_source_serializable,
        }

    def from_dict(self, data: Dict[str, Any]):
        """딕셔너리에서 로드"""
        if not data:
            return

        # 버전 확인
        version = data.get("version", "1.0")

        if version.startswith("2."):
            # v2.0 형식
            self.entries = defaultdict(list, data.get("entries", {}))

            # 보조 인덱스 로드
            for cat, lemmas in data.get("by_category", {}).items():
                self.by_category[cat] = set(lemmas)

            for source, info in data.get("by_source", {}).items():
                self.by_source[source] = {
                    "count": info.get("count", 0),
                    "volumes": set(info.get("volumes", [])),
                }
        else:
            # v1.0 형식 마이그레이션 (기존 형식)
            print("   📦 v1.0 인덱스 감지. v2.0으로 마이그레이션 중...")
            for lemma, entries in data.items():
                if isinstance(entries, list):
                    self.entries[lemma] = entries
            self.rebuild_auxiliary_indices()


# ═══════════════════════════════════════════════════════════════════════════
# 🚀 MAIN LOGIC
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Build/Update Theological Dictionary Lemma Index (v2.0)"
    )
    parser.add_argument("--force", "-f", action="store_true", help="Force full rebuild")
    parser.add_argument(
        "--pretty", "-p", action="store_true", help="Pretty-print JSON output"
    )
    args = parser.parse_args()

    if not ARCHIVE_PATH.exists():
        print(f"❌ Archive path not found: {ARCHIVE_PATH}")
        sys.exit(1)

    print("=" * 60)
    print("📚 Theology AI Lab - Lemma Index Builder v2.0")
    print("=" * 60)
    print(f"📂 Archive: {ARCHIVE_PATH}")

    # 인덱서 초기화
    indexer = EnhancedLemmaIndexer()

    # 기존 인덱스 로드
    if not args.force:
        existing_index = load_json(INDEX_FILE, {})
        indexer.from_dict(existing_index)
        indexer.file_metadata = load_json(META_FILE, {})
        print(f"   기존 인덱스 로드: {len(indexer.entries)} lemmas")
    else:
        print("   강제 재빌드 모드")

    # 현재 파일 스캔
    current_files = {
        f.name: f
        for f in ARCHIVE_PATH.glob("*.json")
        if f.name not in ["lemma_index.json", "lemma_index_meta.json"]
    }

    # 변경 감지
    new_or_modified = []
    deleted_files = set(indexer.file_metadata.keys()) - set(current_files.keys())

    for filename, filepath in current_files.items():
        mtime = filepath.stat().st_mtime
        if filename not in indexer.file_metadata or indexer.file_metadata[filename] != mtime:
            new_or_modified.append(filepath)

    # 변경 없으면 종료
    if not new_or_modified and not deleted_files and not args.force and indexer.entries:
        print("\n✅ 인덱스가 최신 상태입니다!")
        sys.exit(0)

    print(f"\n   변경 감지: {len(new_or_modified)} 신규/수정, {len(deleted_files)} 삭제")

    # 1. 삭제된/수정된 파일 엔트리 제거
    files_to_purge = deleted_files | {f.name for f in new_or_modified}

    if files_to_purge:
        print("\n🧹 기존 엔트리 정리 중...")
        for filename in files_to_purge:
            indexer.purge_file(filename)
            if filename in indexer.file_metadata:
                del indexer.file_metadata[filename]

    # 2. 신규/수정 파일 처리
    if new_or_modified:
        print(f"\n📦 {len(new_or_modified)} 파일 인덱싱 중...")

        for file_path in tqdm(new_or_modified, unit="file"):
            filename = file_path.name
            file_entries = 0

            try:
                for entry in stream_json_entries(file_path):
                    # 필수 필드
                    raw_lemma = get_entry_field(
                        entry, "lemma", "headword", "title", "Lemma", "entry"
                    )
                    page = get_entry_field(entry, "page_number", "page", "Page", "seite")

                    if raw_lemma:
                        # 확장 필드 추출
                        source = get_entry_field(entry, "source", "dict", "dictionary")
                        volume = get_entry_field(entry, "volume", "vol", "band")
                        category = get_entry_field(entry, "category", "categories")
                        language = get_entry_field(entry, "language", "lang")
                        related = get_entry_field(entry, "related_lemmas", "related")

                        # 카테고리가 문자열이면 리스트로 변환
                        if isinstance(category, str):
                            category = [category]

                        indexer.add_entry(
                            lemma=str(raw_lemma),
                            file=filename,
                            page=page,
                            source=source,
                            volume=volume,
                            category=category,
                            language=language,
                            related=related,
                        )
                        file_entries += 1

                # 메타데이터 업데이트
                indexer.file_metadata[filename] = file_path.stat().st_mtime

            except Exception as e:
                print(f"❌ 오류: {filename}: {e}")

    # 3. 보조 인덱스 재구축
    print("\n📊 보조 인덱스 재구축 중...")
    indexer.rebuild_auxiliary_indices()

    # 4. 저장
    print("\n💾 인덱스 저장 중...")
    indent = 2 if args.pretty else None
    save_json(INDEX_FILE, indexer.to_dict(), indent=indent)
    save_json(META_FILE, indexer.file_metadata)

    # 5. 통계 출력
    print("\n" + "=" * 60)
    print("✅ 인덱싱 완료!")
    print("=" * 60)
    print(f"   📝 총 Lemma 수: {len(indexer.entries):,}")
    print(f"   📂 카테고리: {len(indexer.by_category)}")
    print(f"   📚 사전/소스: {len(indexer.by_source)}")

    if indexer.by_category:
        print("\n   카테고리별 분포:")
        for cat, lemmas in sorted(indexer.by_category.items(), key=lambda x: -len(x[1]))[:5]:
            print(f"      - {cat}: {len(lemmas)}")

    if indexer.by_source:
        print("\n   소스별 분포:")
        for source, info in sorted(
            indexer.by_source.items(), key=lambda x: -x[1]["count"]
        )[:5]:
            vols = f" (Vol. {', '.join(map(str, sorted(info['volumes'])))})" if info["volumes"] else ""
            print(f"      - {source}: {info['count']}{vols}")

    print("=" * 60)


if __name__ == "__main__":
    main()
