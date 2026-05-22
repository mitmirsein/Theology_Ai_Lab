#!/usr/bin/env python3
"""
📋 Metadata Parser for Theology AI Lab v5.1
============================================
파일명에서 메타데이터(저자, 제목, 연도)를 자동 추출하는 모듈.

지원 패턴:
1. "Author - Title (Year).ext"    → {author, title, year}
2. "Author_Title_Year.ext"        → {author, title, year}  
3. "Title - Author.ext"           → {title, author}
4. "TDNT_Vol1.pdf"                → {series: TDNT, volume: 1}
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("MetadataParser")

# ============================================================
# Document Type Presets (청크 사이즈 프리셋)
# ============================================================
DOC_TYPE_PRESETS = {
    "dogmatics": {"chunk_size": 2000, "chunk_overlap": 400, "label_ko": "교의학", "label_en": "Dogmatics"},
    "dictionary": {"chunk_size": 1500, "chunk_overlap": 300, "label_ko": "사전", "label_en": "Dictionary"},
    "commentary": {"chunk_size": 1000, "chunk_overlap": 150, "label_ko": "주석", "label_en": "Commentary"},
    "general": {"chunk_size": 1000, "chunk_overlap": 150, "label_ko": "기타", "label_en": "General"},
}

# Theology Fields (신학 분야)
THEOLOGY_FIELDS = [
    ("systematic_theology", "조직신학", "Systematic Theology"),
    ("historical_theology", "역사신학", "Historical Theology"),
    ("biblical_studies", "성서학", "Biblical Studies"),
    ("practical_theology", "실천신학", "Practical Theology"),
    ("philosophical_theology", "철학신학", "Philosophical Theology"),
]

# Known Authors (알려진 저자 패턴)
KNOWN_AUTHORS = {
    "barth": "Karl Barth",
    "bonhoeffer": "Dietrich Bonhoeffer",
    "calvin": "John Calvin",
    "luther": "Martin Luther",
    "tillich": "Paul Tillich",
    "bultmann": "Rudolf Bultmann",
    "moltmann": "Jürgen Moltmann",
    "pannenberg": "Wolfhart Pannenberg",
    "welker": "Michael Welker",
    "jüngel": "Eberhard Jüngel",
    "jungel": "Eberhard Jüngel",
    "schleiermacher": "Friedrich Schleiermacher",
}

# Dictionary Series Patterns
DICT_SERIES = {
    "tdnt": {"name": "Theological Dictionary of the New Testament", "abbr": "TDNT"},
    "nidntt": {"name": "New International Dictionary of NT Theology", "abbr": "NIDNTT"},
    "ednt": {"name": "Exegetical Dictionary of the NT", "abbr": "EDNT"},
    "twot": {"name": "Theological Wordbook of the OT", "abbr": "TWOT"},
    "nidotte": {"name": "New International Dictionary of OT Theology", "abbr": "NIDOTTE"},
    "tre": {"name": "Theologische Realenzyklopädie", "abbr": "TRE"},
    "rgg": {"name": "Religion in Geschichte und Gegenwart", "abbr": "RGG"},
    "ekl": {"name": "Evangelisches Kirchenlexikon", "abbr": "EKL"},
}


@dataclass
class ParsedMetadata:
    """파싱된 메타데이터 구조"""
    author: str = "Unknown"
    title: str = ""
    year: Optional[int] = None
    doc_type: str = "general"
    languages: list = field(default_factory=lambda: ["en"])
    theology_field: str = ""
    tags: list = field(default_factory=list)
    series: Optional[str] = None
    volume: Optional[int] = None
    chunk_size: int = 800
    chunk_overlap: int = 100
    page_offset: int = 0  # 페이지 오프셋 (논리 페이지 1 = 물리 페이지 1 + 오프셋)
    confidence: float = 0.0  # 파싱 신뢰도 (0.0 ~ 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "author": self.author,
            "title": self.title,
            "year": self.year,
            "doc_type": self.doc_type,
            "languages": self.languages,
            "theology_field": self.theology_field,
            "tags": self.tags,
            "series": self.series,
            "volume": self.volume,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "page_offset": self.page_offset,
            "confidence": self.confidence,
        }


class MetadataParser:
    """
    파일명에서 메타데이터를 추출하는 파서.
    """

    # Regex Patterns
    PATTERN_1 = re.compile(
        r"^(?P<author>[^-]+?)\s*-\s*(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*\.(?P<ext>\w+)$"
    )  # "Author - Title (Year).ext"
    
    PATTERN_2 = re.compile(
        r"^(?P<author>[^_]+?)_(?P<title>.+?)_(?P<year>\d{4})\.(?P<ext>\w+)$"
    )  # "Author_Title_Year.ext"
    
    PATTERN_3 = re.compile(
        r"^(?P<title>.+?)\s*-\s*(?P<author>[^(]+?)\.(?P<ext>\w+)$"
    )  # "Title - Author.ext"
    
    PATTERN_DICT = re.compile(
        r"^(?P<series>[A-Za-z]+)[\s_-]*(Vol\.?|Band|Bd\.?)?[\s_]*(?P<volume>\d+)\.(?P<ext>\w+)$",
        re.IGNORECASE
    )  # "TDNT_Vol1.pdf" or "TRE_Bd04.pdf"
    
    YEAR_FALLBACK = re.compile(r"\b(19|20)\d{2}\b")  # 연도 fallback

    def __init__(self):
        self.patterns = [
            (self.PATTERN_1, self._parse_author_title_year),
            (self.PATTERN_2, self._parse_underscore_format),
            (self.PATTERN_DICT, self._parse_dictionary_series),
            (self.PATTERN_3, self._parse_title_author),
        ]

    def parse(self, file_path: str) -> ParsedMetadata:
        """
        파일 경로에서 메타데이터를 추출합니다.
        
        Args:
            file_path: 파일 경로 (전체 경로 또는 파일명만)
            
        Returns:
            ParsedMetadata 객체
        """
        path = Path(file_path)
        filename = path.name
        stem = path.stem  # 확장자 제외
        
        logger.info(f"🔍 Parsing filename: {filename}")
        
        # 1. 패턴 매칭 시도
        for pattern, handler in self.patterns:
            match = pattern.match(filename)
            if match:
                result = handler(match, stem)
                if result.confidence > 0.5:
                    logger.info(f"✅ Pattern matched with confidence {result.confidence:.2f}")
                    return self._enrich_metadata(result, file_path)
        
        # 2. Fallback: 기본 파싱
        logger.info("⚠️ No pattern matched, using fallback parsing")
        return self._fallback_parse(file_path)

    def _parse_author_title_year(self, match: re.Match, stem: str) -> ParsedMetadata:
        """'Author - Title (Year).ext' 패턴 처리"""
        author_raw = match.group("author").strip()
        title = match.group("title").strip()
        year = int(match.group("year"))
        
        author = self._normalize_author(author_raw)
        
        return ParsedMetadata(
            author=author,
            title=title,
            year=year,
            confidence=0.9
        )

    def _parse_underscore_format(self, match: re.Match, stem: str) -> ParsedMetadata:
        """'Author_Title_Year.ext' 패턴 처리"""
        author_raw = match.group("author").replace("_", " ").strip()
        title = match.group("title").replace("_", " ").strip()
        year = int(match.group("year"))
        
        author = self._normalize_author(author_raw)
        
        return ParsedMetadata(
            author=author,
            title=title,
            year=year,
            confidence=0.85
        )

    def _parse_title_author(self, match: re.Match, stem: str) -> ParsedMetadata:
        """'Title - Author.ext' 패턴 처리"""
        title = match.group("title").strip()
        author_raw = match.group("author").strip()
        
        author = self._normalize_author(author_raw)
        
        # 연도 추출 시도
        year = self._extract_year_fallback(stem)
        
        return ParsedMetadata(
            author=author,
            title=title,
            year=year,
            confidence=0.7
        )

    def _parse_dictionary_series(self, match: re.Match, stem: str) -> ParsedMetadata:
        """'TDNT_Vol1.pdf' 같은 사전 시리즈 패턴 처리"""
        series_key = match.group("series").lower()
        volume = int(match.group("volume"))
        
        series_info = DICT_SERIES.get(series_key, {"name": series_key.upper(), "abbr": series_key.upper()})
        
        return ParsedMetadata(
            author="Various",
            title=f"{series_info['abbr']} Volume {volume}",
            doc_type="dictionary",
            series=series_info["abbr"],
            volume=volume,
            chunk_size=DOC_TYPE_PRESETS["dictionary"]["chunk_size"],
            chunk_overlap=DOC_TYPE_PRESETS["dictionary"]["chunk_overlap"],
            confidence=0.95
        )

    def _normalize_author(self, author_raw: str) -> str:
        """저자명을 정규화합니다."""
        author_lower = author_raw.lower().replace("_", " ").strip()
        
        # Known authors lookup
        for key, full_name in KNOWN_AUTHORS.items():
            if key in author_lower:
                return full_name
        
        # Capitalize each word
        return " ".join(word.capitalize() for word in author_raw.split())

    def _extract_year_fallback(self, text: str) -> Optional[int]:
        """텍스트에서 연도 추출 (fallback)"""
        match = self.YEAR_FALLBACK.search(text)
        if match:
            return int(match.group())
        return None

    def _detect_doc_type(self, file_path: str, title: str) -> str:
        """도서 유형 자동 감지"""
        path_lower = file_path.lower()
        title_lower = title.lower() if title else ""
        
        # Dictionary keywords
        dict_keywords = ["dictionary", "lexicon", "사전", "wörterbuch", "tdnt", "nidntt", "tre", "rgg"]
        if any(k in path_lower or k in title_lower for k in dict_keywords):
            return "dictionary"
        
        # Commentary keywords
        comm_keywords = ["commentary", "kommentar", "주석", "exegesis"]
        if any(k in path_lower or k in title_lower for k in comm_keywords):
            return "commentary"
        
        # Philosophy keywords
        phil_keywords = ["philosophy", "philosophie", "철학", "hegel", "kant", "heidegger"]
        if any(k in path_lower or k in title_lower for k in phil_keywords):
            return "philosophy"
        
        return "dogmatics"

    def _detect_languages(self, file_path: str) -> list:
        """파일 경로에서 언어 감지"""
        path_lower = file_path.lower()
        languages = []
        
        if any(k in path_lower for k in ["german", "deutsch", "_de_", "_deu"]):
            languages.append("de")
        if any(k in path_lower for k in ["korean", "한국", "_ko_", "_kor"]):
            languages.append("ko")
        if any(k in path_lower for k in ["english", "_en_", "_eng"]):
            languages.append("en")
            
        return languages if languages else ["en"]

    def _enrich_metadata(self, meta: ParsedMetadata, file_path: str) -> ParsedMetadata:
        """메타데이터를 추가 정보로 보강"""
        # Doc type detection
        if meta.doc_type == "general":
            meta.doc_type = self._detect_doc_type(file_path, meta.title)
        
        # Apply preset
        preset = DOC_TYPE_PRESETS.get(meta.doc_type, DOC_TYPE_PRESETS["general"])
        meta.chunk_size = preset["chunk_size"]
        meta.chunk_overlap = preset["chunk_overlap"]
        
        # Language detection
        if meta.languages == ["en"]:
            meta.languages = self._detect_languages(file_path)
        
        return meta

    def _fallback_parse(self, file_path: str) -> ParsedMetadata:
        """패턴 매칭 실패 시 기본 파싱"""
        path = Path(file_path)
        stem = path.stem
        
        # Clean up filename
        title = stem.replace("_", " ").replace("-", " ").strip()
        
        # Try to extract year
        year = self._extract_year_fallback(stem)
        
        # Detect doc type
        doc_type = self._detect_doc_type(file_path, title)
        preset = DOC_TYPE_PRESETS.get(doc_type, DOC_TYPE_PRESETS["general"])
        
        return ParsedMetadata(
            author="Unknown",
            title=title,
            year=year,
            doc_type=doc_type,
            languages=self._detect_languages(file_path),
            chunk_size=preset["chunk_size"],
            chunk_overlap=preset["chunk_overlap"],
            confidence=0.3
        )


# ============================================================
# Convenience Function
# ============================================================
def parse_filename(file_path: str) -> Dict[str, Any]:
    """
    파일 경로에서 메타데이터를 추출하는 편의 함수.
    
    Args:
        file_path: 파일 경로
        
    Returns:
        메타데이터 딕셔너리
    """
    parser = MetadataParser()
    result = parser.parse(file_path)
    return result.to_dict()


# ============================================================
# Test
# ============================================================
if __name__ == "__main__":
    test_files = [
        "Michael Welker - In God's Image (2021).epub",
        "Barth_KD_I_1_1932.pdf",
        "Church Dogmatics - Karl Barth.pdf",
        "TDNT_Vol1.pdf",
        "TRE_Bd04.pdf",
        "random_document.txt",
    ]
    
    parser = MetadataParser()
    for f in test_files:
        print(f"\n📄 {f}")
        result = parser.parse(f)
        print(f"   Author: {result.author}")
        print(f"   Title: {result.title}")
        print(f"   Year: {result.year}")
        print(f"   Type: {result.doc_type}")
        print(f"   Chunk: {result.chunk_size}/{result.chunk_overlap}")
        print(f"   Confidence: {result.confidence:.2f}")
