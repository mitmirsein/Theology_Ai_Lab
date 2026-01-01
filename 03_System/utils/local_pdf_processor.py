#!/usr/bin/env python3
"""
로컬 PDF 프로세서 - Theology Dictionary Indexing (v2.1)
Colab 없이 로컬에서 PDF를 ChromaDB JSON으로 변환

Features:
- Volume/Lemma 자동 추출
- 토큰 기반 스마트 청킹
- ChromaDB 호환 JSON 출력
- [v2.0] 확장 메타데이터 (category, language, related_lemmas)
- [v2.1] 페이지 번호 자동 감지 (pdf_page vs print_page)
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

try:
    import tiktoken
except ImportError:
    tiktoken = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None

try:
    from ebooklib import epub
    from bs4 import BeautifulSoup
    EPUB_AVAILABLE = True
except ImportError:
    EPUB_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════════════════════════════

# 사전 약어 매칭
DICTIONARY_ABBREVS = {
    "TDNT": "Theological Dictionary of the New Testament",
    "NIDNTT": "New International Dictionary of NT Theology",
    "EDNT": "Exegetical Dictionary of the NT",
    "ThWAT": "Theologisches Wörterbuch zum Alten Testament",
    "EWNT": "Exegetisches Wörterbuch zum Neuen Testament",
    "EKL": "Evangelisches Kirchenlexikon",
    "RGG": "Religion in Geschichte und Gegenwart",
    "HWPh": "Historisches Wörterbuch der Philosophie",
    "TRE": "Theologische Realenzyklopädie",
    "Theologische": "TRE",
    "KD": "Kirchliche Dogmatik",
}

# ═══════════════════════════════════════════════════════════════════
# [v2.0] 확장 메타데이터 유틸리티
# ═══════════════════════════════════════════════════════════════════

# 카테고리 추론 패턴
CATEGORY_PATTERNS = {
    "biblical_figures": r"(?:Abraham|Moses|David|Jesus|Paul|Paulus|Jakob|Isaak|Petrus|Johannes|Elijah|Elias)",
    "systematic_theology": r"(?:Gnade|Rechtfertigung|Trinität|Sünde|Erlösung|Sakrament|Taufe|Abendmahl|Eschatologie)",
    "church_history": r"(?:Luther|Calvin|Reformation|Konzil|Augustin|Barth|Schleiermacher|Kirchen(?:geschicht|väter))",
    "philosophy": r"(?:Kant|Hegel|Aristoteles|Platon|Nietzsche|Heidegger|Philosophie|Metaphysik|Ontologie)",
    "biblical_studies": r"(?:Exegese|Hermeneutik|Septuaginta|Pentateuch|Evangelium|Apostel|Propheten)",
    "ethics": r"(?:Ethik|Moral|Tugend|Pflicht|Gewissen|Verantwortung)",
    "practical_theology": r"(?:Predigt|Seelsorge|Liturgie|Gottesdienst|Gemeinde|Mission)",
}


def detect_language(text: str) -> str:
    """
    텍스트의 주요 언어 감지

    Returns:
        언어 코드: grc (그리스어), heb (히브리어), de (독일어), en (영어), unknown
    """
    # 그리스어 문자 확인
    if re.search(r'[α-ωά-ώΑ-Ω]', text):
        return "grc"
    # 히브리어 문자 확인
    if re.search(r'[א-ת]', text):
        return "heb"
    # 독일어 특성 단어
    if re.search(r'\b(der|die|das|und|ist|nicht|auch|mit|für|von)\b', text, re.I):
        return "de"
    # 영어 특성 단어
    if re.search(r'\b(the|and|is|of|to|in|that|for|with)\b', text, re.I):
        return "en"
    # 한국어 확인
    if re.search(r'[가-힣]', text):
        return "ko"
    return "unknown"


def extract_category(lemma: str, text: str) -> List[str]:
    """
    표제어와 내용에서 카테고리 추론

    Args:
        lemma: 표제어
        text: 청크 텍스트

    Returns:
        카테고리 목록 (예: ["systematic_theology", "church_history"])
    """
    categories = []
    search_text = f"{lemma or ''} {text[:500]}"

    for cat, pattern in CATEGORY_PATTERNS.items():
        if re.search(pattern, search_text, re.I):
            categories.append(cat)

    return categories if categories else ["general"]


def extract_related_lemmas(text: str) -> List[str]:
    """
    텍스트에서 관련 표제어 추출

    신학 사전의 참조 패턴:
    - "→ Liebe"
    - "siehe Glaube"
    - "vgl. Hoffnung"
    - "s. auch Gericht"
    - "cf. Grace"

    Returns:
        관련 표제어 목록
    """
    patterns = [
        # 독일어 참조
        r'(?:→|siehe|vgl\.?|s\.(?:\s*auch)?|vergleiche)\s+([A-ZÄÖÜ][a-zäöüß]+)',
        # 영어 참조
        r'(?:cf\.?|see|see also|compare)\s+([A-Z][a-z]+)',
        # 그리스어 참조 (대문자로 시작)
        r'(?:→|cf\.?)\s+([Α-Ω][α-ω]+)',
    ]

    related = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.I)
        related.update(matches)

    return list(related)[:10]  # 최대 10개

# ═══════════════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════════════

def tiktoken_len(text: str) -> int:
    """토큰 수를 정확하게 측정"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except:
        return len(text) // 4  # 대략적 추정


def extract_dictionary_info(filename: str) -> Tuple[str, Optional[int]]:
    """
    파일명에서 사전 약어와 권 번호 추출
    
    Examples:
        'ThWAT_Vol1.pdf' -> ('ThWAT', 1)
        'EWNT_Bd2.pdf' -> ('EWNT', 2)
        'HWPh.pdf' -> ('HWPh', None)
    """
    stem = Path(filename).stem
    
    # 사전 약어 추출
    dict_abbrev = None
    for abbrev, full_name in DICTIONARY_ABBREVS.items():
        if abbrev.lower() in stem.lower():
            # "Theologische" 매칭 시 "TRE"로 변환
            dict_abbrev = "TRE" if abbrev == "Theologische" else abbrev
            break
    
    if not dict_abbrev:
        dict_abbrev = stem.split('_')[0].split()[0].upper()
    
    # 권 번호 추출
    volume_patterns = [
        r'(?:Vol|Bd|Band|권|V)[.\-_\s]?(\d+)',
        r'(\d+)(?:\s*권|\s*Bd)',
        r'[,\s](\d+)[\s,]',
        r'\s(\d+)[\s_-]',
        r'_(\d+)$',
    ]
    
    volume = None
    for pattern in volume_patterns:
        match = re.search(pattern, stem, re.IGNORECASE)
        if match:
            volume = int(match.group(1))
            break
    
    return dict_abbrev, volume


def extract_lemma(text: str) -> Optional[str]:
    """
    텍스트 시작 부분에서 표제어(Lemma) 추출
    
    신학 사전 표제어 패턴:
    - 전체 대문자: "GNADE", "ABRAHAM"
    - 독일어: "Alkohol und Alkoholismus"
    - 그리스/히브리어: "ἀγάπη", "חֶסֶד"
    """
    sample = text.strip()[:300]
    
    patterns = [
        # 전체 대문자 (TDNT 스타일)
        r'^([A-ZÄÖÜ]{2,}(?:\s+[A-ZÄÖÜ]{2,})*)[\.,\s]',
        
        # 독일어/영어 (HWPh, ThWAT 스타일)
        r'^([A-ZÄÖÜ][a-zäöüß]+(?:\s+(?:und|u\.|,|/)\s*[A-ZÄÖÜ]?[a-zäöüß]+)*)[\.,]',
        
        # 그리스어
        r'^([α-ωά-ώΑ-Ω]+)[\s,\.]',
        
        # 히브리어
        r'^([א-ת]+)[\s,\.]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, sample)
        if match:
            lemma = match.group(1).strip()
            if 2 <= len(lemma) <= 50:
                return lemma
    
    return None


# ═══════════════════════════════════════════════════════════════════
# PDF 처리
# ═══════════════════════════════════════════════════════════════════

def process_file(
    file_path: str,
    text_splitter,
    page_offset: int = 0,
    double_page: bool = False,
    auto_detect_pages: bool = False,
) -> List[Dict[str, Any]]:
    """
    파일(PDF 또는 TXT)을 처리하여 메타데이터가 포함된 청크 리스트 반환

    Args:
        file_path: 입력 파일 경로
        text_splitter: 텍스트 스플리터
        page_offset: 수동 페이지 오프셋 (pdf_page - offset = print_page)
        double_page: 스프레드(양면) 모드
        auto_detect_pages: [v2.1] 페이지 번호 자동 감지 (OCR 기반)
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == '.pdf':
        return _process_pdf_content(file_path, text_splitter, page_offset, double_page, auto_detect_pages)
    elif suffix == '.txt':
        return _process_text_content(file_path, text_splitter, page_offset)
    elif suffix == '.epub':
        return _process_epub_content(file_path, text_splitter)
    else:
        print(f"      ⚠️ 지원하지 않는 파일 형식: {suffix}")
        return []


def _process_epub_content(epub_path: str, text_splitter) -> List[Dict[str, Any]]:
    """
    EPUB 파일 처리 - 챕터별 텍스트 추출 및 청킹
    
    Args:
        epub_path: EPUB 파일 경로
        text_splitter: 텍스트 스플리터
    
    Returns:
        청크 리스트 (메타데이터 포함)
    """
    if not EPUB_AVAILABLE:
        print("      ❌ EPUB 처리를 위해 'ebooklib'과 'beautifulsoup4'를 설치하세요:")
        print("         pip install ebooklib beautifulsoup4")
        return []
    
    filename = Path(epub_path).name
    dict_abbrev, volume = extract_dictionary_info(filename)
    
    print(f"   📖 {filename}")
    print(f"      형식: EPUB, 소스: {dict_abbrev}")
    
    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        print(f"      ❌ EPUB 읽기 오류: {e}")
        return []
    
    # 챕터별 텍스트 추출
    chapters_data = []
    chapter_num = 0
    
    for item in book.get_items():
        if item.get_type() == epub.ITEM_DOCUMENT:
            chapter_num += 1
            content = item.get_content().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
            
            # HTML 태그 제거, 텍스트만 추출
            text = soup.get_text(separator='\n', strip=True)
            
            if text.strip():
                chapters_data.append({
                    'chapter_num': chapter_num,
                    'chapter_id': item.get_id(),
                    'text': text,
                    'char_start': sum(len(c['text']) for c in chapters_data)
                })
    
    if not chapters_data:
        print(f"      ⚠️ EPUB에서 텍스트를 추출할 수 없습니다.")
        return []
    
    print(f"      📚 {len(chapters_data)}개 챕터 발견")
    
    # 전체 텍스트 통합 및 청킹
    full_text = "\n\n".join(c['text'] for c in chapters_data)
    chunks = text_splitter.split_text(full_text)
    
    # 표제어 감지
    chunk_lemmas = []
    current_lemma = None
    for chunk in chunks:
        detected = extract_lemma(chunk)
        if detected:
            current_lemma = detected
        chunk_lemmas.append(current_lemma)
    
    # 표제어별 청크 수 계산
    lemma_chunk_counts = defaultdict(int)
    for lemma in chunk_lemmas:
        if lemma:
            lemma_chunk_counts[lemma] += 1
    
    # 청크 메타데이터 생성
    result = []
    char_position = 0
    lemma_current_index = defaultdict(int)
    
    for i, chunk in enumerate(chunks):
        chunk_mid = char_position + len(chunk) // 2
        
        # 해당 챕터 찾기
        chapter_num = 1
        for ch in chapters_data:
            if chunk_mid >= ch['char_start']:
                chapter_num = ch['chapter_num']
            else:
                break
        
        # 표제어 정보
        lemma = chunk_lemmas[i]
        if lemma:
            lemma_current_index[lemma] += 1
            lemma_idx = lemma_current_index[lemma]
            lemma_total = lemma_chunk_counts[lemma]
        else:
            lemma_idx = None
            lemma_total = None
        
        # 확장 메타데이터
        language = detect_language(chunk)
        categories = extract_category(lemma, chunk)
        related = extract_related_lemmas(chunk)
        
        metadata = {
            "source": dict_abbrev,
            "filename": filename,
            "chunk_id": f"chunk_{i}",
            "chapter": chapter_num,
            "total_chapters": len(chapters_data),
            "chunk_tokens": tiktoken_len(chunk),
            "volume": volume,
            "lemma": lemma,
            "lemma_chunk_index": lemma_idx,
            "lemma_total_chunks": lemma_total,
            "file_type": "epub",
            "language": language,
            "category": categories,
            "related_lemmas": related,
        }
        
        # ID 생성
        chunk_id = f"{dict_abbrev}"
        if volume:
            chunk_id += f"_{volume}"
        if lemma:
            chunk_id += f"_{lemma[:20]}"
        chunk_id += f"_{i:04d}"
        
        result.append({
            "id": chunk_id,
            "text": chunk,
            "metadata": metadata
        })
        
        char_position += len(chunk)
    
    unique_lemmas = len([l for l in set(chunk_lemmas) if l])
    print(f"      ✅ {len(result):,}개 청크 생성 ({unique_lemmas}개 표제어 감지)")
    
    return result

def _process_text_content(txt_path: str, text_splitter, page_offset: int) -> List[Dict[str, Any]]:
    """TXT 파일 처리 (페이지 구분 없음 또는 간단한 구분)"""
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"      ❌ 파일 읽기 오류: {e}")
        return []

    # 텍스트 청킹
    chunks = text_splitter.split_text(text)
    
    # 메타데이터 생성 (TXT는 페이지 개념이 모호하므로 전체 1페이지로 가정하거나 별도 로직 필요)
    filename = Path(txt_path).name
    dict_abbrev, volume = extract_dictionary_info(filename)
    
    result = []
    chunk_lemmas = []
    
    # 1. 표제어 감지
    current_lemma = None
    for chunk in chunks:
        detected = extract_lemma(chunk)
        if detected:
            current_lemma = detected
        chunk_lemmas.append(current_lemma)
        
    # 2. 표제어 카운트
    lemma_chunk_counts = defaultdict(int)
    for lemma in chunk_lemmas:
        if lemma: lemma_chunk_counts[lemma] += 1
        
    lemma_current_index = defaultdict(int)
    
    for i, chunk in enumerate(chunks):
        lemma = chunk_lemmas[i]
        if lemma:
            lemma_current_index[lemma] += 1
            lemma_idx = lemma_current_index[lemma]
            lemma_total = lemma_chunk_counts[lemma]
        else:
            lemma_idx = None
            lemma_total = None
            
        # [v2.0] 확장 메타데이터
        language = detect_language(chunk)
        categories = extract_category(lemma, chunk)
        related = extract_related_lemmas(chunk)

        metadata = {
            "source": dict_abbrev,
            "filename": filename,
            "chunk_id": f"chunk_{i}",
            "page_number": 1,  # TXT는 기본 1
            "pdf_page": 1,
            "total_pages": 1,
            "chunk_tokens": tiktoken_len(chunk),
            "volume": volume,
            "lemma": lemma,
            "lemma_chunk_index": lemma_idx,
            "lemma_total_chunks": lemma_total,
            "is_spread": False,
            # [v2.0] 확장 필드
            "language": language,
            "category": categories,
            "related_lemmas": related,
        }
        
        chunk_id = f"{dict_abbrev}"
        if volume: chunk_id += f"_{volume}"
        if lemma: chunk_id += f"_{lemma[:20]}"
        chunk_id += f"_{i:04d}"
        
        result.append({
            "id": chunk_id,
            "text": chunk,
            "metadata": metadata
        })
        
    print(f"      ✅ {len(result):,}개 텍스트 청크 생성")
    return result

def _process_pdf_content(
    pdf_path: str,
    text_splitter,
    page_offset: int = 0,
    double_page: bool = False,
    auto_detect_pages: bool = False,
) -> List[Dict[str, Any]]:
    """
    PDF 내용을 처리하는 내부 함수

    [v2.1] 페이지 매핑 우선순위:
      1. .mapping.json 파일 (사용자 수동 매핑)
      2. auto_detect_pages=True (OCR 자동 감지)
      3. page_offset (단순 오프셋)
    """
    # [v2.1] 페이지 매핑 로드
    page_mapping = {}  # pdf_page → print_page
    mapping_source = None

    # 1순위: .mapping.json 파일 확인
    try:
        from page_mapping_loader import load_mapping_file
        mapping_result = load_mapping_file(pdf_path)
        if mapping_result:
            page_mapping = mapping_result.page_map
            mapping_source = f"매핑 파일 ({mapping_result.info})"
            print(f"      ✅ {mapping_source}")
    except ImportError:
        pass
    except Exception as e:
        print(f"      ⚠️ 매핑 파일 로드 실패: {e}")

    # 2순위: 자동 감지 (매핑 파일 없을 시)
    if not page_mapping and auto_detect_pages:
        try:
            from page_number_detector import PageNumberDetector
            detector = PageNumberDetector()
            results = detector.detect_page_numbers(pdf_path, sample_pages=30, use_ocr=True)
            page_mapping = detector.create_offset_map(results)
            mapping_source = "자동 감지"
            print(f"      ✨ 페이지 자동 감지 완료: {len(page_mapping)}페이지 매핑됨")
        except ImportError:
            print(f"      ⚠️ page_number_detector 모듈 없음")
        except Exception as e:
            print(f"      ⚠️ 페이지 감지 실패: {e}, 수동 오프셋 사용")
    # ═══════════════════════════════════════════════════════════════════
    # 📖 Double Page / Layout 처리 (TRE Bd.4 전용 매핑 포함)
    # ═══════════════════════════════════════════════════════════════════
    
    def get_tre_bd4_pages(pdf_page: int) -> Tuple[Optional[int], Optional[int]]:
        """TRE Bd.4 전용 불규칙 매핑 로직"""
        if pdf_page < 2: return None, None
        if pdf_page == 2: return None, 1
        if 3 <= pdf_page <= 88:
            return (pdf_page - 2) * 2, (pdf_page - 2) * 2 + 1
        if pdf_page == 89: return 174, None  # Right is blank
        if pdf_page == 90: return None, 175  # Left is blank
        if 91 <= pdf_page <= 266:
            return (pdf_page - 3) * 2, (pdf_page - 3) * 2 + 1
        if pdf_page == 267: return 528, None  # Right is Tafel
        if pdf_page == 268: return None, 529  # Left is Tafel
        if pdf_page >= 269:
            return (pdf_page - 4) * 2, (pdf_page - 4) * 2 + 1
        return None, None

    def get_tre_bd5_pages(pdf_page: int) -> Tuple[Optional[int], Optional[int]]:
        """TRE Bd.5 전용 불규칙 매핑 로직"""
        if pdf_page < 2: return None, None
        if pdf_page == 2: return None, 1
        if 3 <= pdf_page <= 125:
            return (pdf_page - 2) * 2, (pdf_page - 2) * 2 + 1
        if pdf_page == 126: return 248, None
        if pdf_page == 127: return None, None
        if pdf_page == 128: return None, 249
        if 129 <= pdf_page <= 259:
            return (pdf_page - 4) * 2, (pdf_page - 4) * 2 + 1
        if pdf_page == 260: return 512, None
        if 261 <= pdf_page <= 262: return None, None
        if pdf_page == 263: return None, 513
        if pdf_page >= 264:
            return (pdf_page - 7) * 2, (pdf_page - 7) * 2 + 1
        return None, None

    def get_kd_ii2_page(pdf_page: int) -> Optional[int]:
        """KD II/2 전용 구간별 오프셋 매핑"""
        if pdf_page < 10: return None
        if 10 <= pdf_page <= 716:
            return pdf_page - 9
        if 717 <= pdf_page <= 874:
            return pdf_page - 10
        if 875 <= pdf_page <= 885:
            return pdf_page - 12
        if pdf_page >= 886:
            return pdf_page - 11
        return None

    def get_kd_iv4_page(pdf_page: int) -> Optional[int]:
        """KD IV/4 전용 오프셋 매핑 (PDF 13 -> 종이 2, 오프셋 11)"""
        if pdf_page < 13: return None
        return pdf_page - 11

    def split_double_page(page) -> Tuple[str, str]:
        """PDF 페이지를 좌/우 텍스트로 분할 (좌표 기반)"""
        left_parts = []
        right_parts = []
        middle = float(page.mediabox.width) / 2
        
        # 텍스트 조각과 좌표 수집
        parts = []
        def visitor(text, cm, tm, font_dict, font_size):
            if text.strip():
                parts.append({
                    'text': text,
                    'x': tm[4],
                    'y': tm[5]
                })
        
        page.extract_text(visitor_text=visitor)
        
        # Y좌표(위->아래) 순으로 정렬 (pypdf 추출 순서가 꼬일 수 있음)
        parts.sort(key=lambda p: (-p['y'], p['x']))
        
        for p in parts:
            if p['x'] < middle:
                left_parts.append(p['text'])
            else:
                right_parts.append(p['text'])
                
        return "".join(left_parts), "".join(right_parts)

    filename = Path(pdf_path).name
    dict_abbrev, volume = extract_dictionary_info(filename)
    is_tre_bd4 = (dict_abbrev == "TRE" and volume == 4)
    is_tre_bd5 = (dict_abbrev == "TRE" and volume == 5)
    stem_lower = Path(filename).stem.lower()
    is_kd_ii2 = ("kd" in stem_lower and ("ii-2" in stem_lower or "ii.2" in stem_lower or "ii_2" in stem_lower))
    is_kd_iv4 = ("kd" in stem_lower and ("iv-4" in stem_lower or "iv.4" in stem_lower or "iv_4" in stem_lower))
    
    print(f"   📖 {filename}")
    print(f"      사전: {dict_abbrev}, 권: {volume or '단권'}")
    if double_page:
        mode_str = "TRE Bd.4 특수 매핑" if is_tre_bd4 else ("TRE Bd.5 특수 매핑" if is_tre_bd5 else "일반 스프레드")
        print(f"      ✨ 스프레드 모드 활성화 ({mode_str})")
    elif is_kd_ii2:
        print(f"      ✨ KD II.2 특수 구간 매핑 활성화")
    elif is_kd_iv4:
        print(f"      ✨ KD IV/4 기본 오프셋(-11) 매핑 활성화")
    
    # PDF 읽기
    reader = PdfReader(pdf_path)
    
    # 페이지 텍스트 수집
    pages_data = []
    total_pages = len(reader.pages)
    
    for page_num, page in enumerate(reader.pages, 1):
        # 10페이지마다 또는 마지막 페이지에 진행률 출력
        if page_num % 10 == 0 or page_num == total_pages:
            print(f"[PROGRESS] {int(page_num / total_pages * 50)}% (텍스트 추출 중...)")
        if double_page:
            left_txt, right_txt = split_double_page(page)
            
            # 페이지 번호 결정
            if is_tre_bd4:
                lp, rp = get_tre_bd4_pages(page_num)
            elif is_tre_bd5:
                lp, rp = get_tre_bd5_pages(page_num)
            else:
                # 기본 스프레드 공식
                lp = (page_num - page_offset) * 2 - 1
                rp = (page_num - page_offset) * 2
            
            if left_txt.strip() and lp:
                pages_data.append({
                    'page_num': lp,
                    'pdf_page': page_num,
                    'text': left_txt,
                    'char_start': sum(len(p['text']) for p in pages_data)
                })
            if right_txt.strip() and rp:
                pages_data.append({
                    'page_num': rp,
                    'pdf_page': page_num,
                    'text': right_txt,
                    'char_start': sum(len(p['text']) for p in pages_data)
                })
        else:
            text = page.extract_text() or ""
            if text.strip():
                # KD II.2 특수 매핑 또는 일반 오프셋 매핑 적용
                if is_kd_ii2:
                    p_num = get_kd_ii2_page(page_num)
                elif is_kd_iv4:
                    p_num = get_kd_iv4_page(page_num)
                else:
                    p_num = max(1, page_num - page_offset)
                
                if p_num:
                    pages_data.append({
                        'page_num': p_num,
                        'pdf_page': page_num,
                        'text': text,
                        'char_start': sum(len(p['text']) for p in pages_data)
                    })
    
    if not pages_data:
        print(f"      ⚠️  빈 PDF")
        return []
    
    # 텍스트 통합 및 청킹
    full_text = "\n\n".join(p['text'] for p in pages_data)
    print(f"[PROGRESS] 60% (청킹 시작...)")
    chunks = text_splitter.split_text(full_text)
    
    # 표제어 감지 (1차 패스)
    chunk_lemmas = []
    current_lemma = None
    for chunk in chunks:
        detected = extract_lemma(chunk)
        if detected:
            current_lemma = detected
        chunk_lemmas.append(current_lemma)
    
    # 표제어별 청크 수 계산 (2차 패스)
    lemma_chunk_counts = defaultdict(int)
    for lemma in chunk_lemmas:
        if lemma:
            lemma_chunk_counts[lemma] += 1
    
    # 청크 메타데이터 생성 (3차 패스)
    result = []
    char_position = 0
    lemma_current_index = defaultdict(int)
    
    for i, chunk in enumerate(chunks):
        chunk_mid = char_position + len(chunk) // 2
        
        # 페이지 번호 및 원본 PDF 페이지 찾기
        page_num = 1
        pdf_page = 1
        for p in pages_data:
            if chunk_mid >= p['char_start']:
                page_num = p['page_num']
                pdf_page = p.get('pdf_page', page_num)
            else:
                break
        
        # 표제어 정보
        lemma = chunk_lemmas[i]
        if lemma:
            lemma_current_index[lemma] += 1
            lemma_idx = lemma_current_index[lemma]
            lemma_total = lemma_chunk_counts[lemma]
        else:
            lemma_idx = None
            lemma_total = None
        
        # [v2.0] 확장 메타데이터
        language = detect_language(chunk)
        categories = extract_category(lemma, chunk)
        related = extract_related_lemmas(chunk)

        # [v2.1] 실제 인쇄본 페이지 번호 결정
        # 우선순위: 자동 감지 > 수동 오프셋 > 기존 page_num
        if page_mapping and pdf_page in page_mapping:
            print_page = page_mapping[pdf_page]
        elif page_offset:
            print_page = max(1, pdf_page - page_offset)
        else:
            print_page = page_num  # 기존 로직 유지

        # 메타데이터
        metadata = {
            "source": dict_abbrev,
            "filename": filename,
            "chunk_id": f"chunk_{i}",
            "page_number": page_num,       # 기존 호환용 (deprecated)
            "pdf_page": pdf_page,          # PDF 물리적 페이지
            "print_page": print_page,      # [v2.1] 실제 인쇄본 페이지
            "total_pages": len(reader.pages),
            "chunk_tokens": tiktoken_len(chunk),
            "volume": volume,
            "lemma": lemma,
            "lemma_chunk_index": lemma_idx,
            "lemma_total_chunks": lemma_total,
            "is_spread": double_page,
            # [v2.0] 확장 필드
            "language": language,
            "category": categories,
            "related_lemmas": related,
        }
        
        # ID 생성
        chunk_id = f"{dict_abbrev}"
        if volume:
            chunk_id += f"_{volume}"
        if lemma:
            chunk_id += f"_{lemma[:20]}"
        chunk_id += f"_{i:04d}"
        
        result.append({
            "id": chunk_id,
            "text": chunk,
            "metadata": metadata
        })
        
        char_position += len(chunk)
        
        # 청킹 진행률 (60% ~ 100%)
        if i % 50 == 0 or i == len(chunks) - 1:
            prog = 60 + int((i + 1) / len(chunks) * 40)
            print(f"[PROGRESS] {prog}% (청크 메타데이터 생성 중...)")
    
    # 통계
    unique_lemmas = len([l for l in set(chunk_lemmas) if l])
    print(f"      ✅ {len(result):,}개 청크 생성 ({unique_lemmas}개 표제어 감지)")
    
    return result


# ═══════════════════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='PDF를 ChromaDB용 JSON으로 변환'
    )
    parser.add_argument('input', help='PDF 파일 또는 폴더 경로')
    parser.add_argument('-o', '--output', default=os.path.expanduser("~/Desktop/MS_Brain.nosync/300 Tech/320 Coding/Projects.nosync/Theology_Project.nosync/inbox"),
                        help='출력 폴더 (기본: inbox)')
    parser.add_argument('--chunk-size', type=int, default=2800,
                        help='청크 크기 (문자 수)')
    parser.add_argument('--overlap', type=int, default=560,
                        help='청크 오버랩 (문자 수)')
    parser.add_argument('--page-offset', type=int, default=0,
                        help='PDF페이지 - 오프셋 = 종이책 페이지 (예: TRE는 2)')
    parser.add_argument('--double-page', action='store_true',
                        help='PDF 1페이지에 종이책 2페이지가 포함된 경우(스프레드)')
    parser.add_argument('--auto-detect', action='store_true',
                        help='[v2.1] 페이지 번호 자동 감지 (OCR 기반)')

    args = parser.parse_args()
    
    # 출력 폴더 생성
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if RecursiveCharacterTextSplitter is None:
        print("❌ 'langchain-text-splitters' 패키지가 설치되지 않았습니다.")
        sys.exit(1)

    # 텍스트 스플리터 설정
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=args.chunk_size,
        chunk_overlap=args.overlap,
        separators=["\n\n\n", "\n\n", "\n", ". ", "! ", "? ", "; ", " ", ""],
        length_function=tiktoken_len,
        is_separator_regex=False,
    )
    
    print("=" * 60)
    print("📚 로컬 PDF → ChromaDB JSON 변환")
    print("=" * 60)
    print(f"\n입력: {args.input}")
    print(f"출력: {output_dir}")
    print(f"청킹: ~{args.chunk_size//4} 토큰 (오버랩 ~{args.overlap//4})\n")
    
    # 입력 경로 확인
    input_path = Path(args.input)
    
    if input_path.is_file():
        input_files = [input_path]
    elif input_path.is_dir():
        input_files = list(input_path.glob("*.pdf")) + list(input_path.glob("*.txt"))
    else:
        print(f"❌ 경로를 찾을 수 없습니다: {args.input}")
        return
    
    if not input_files:
        print("❌ 처리할 파일(PDF/TXT)을 찾을 수 없습니다.")
        return
    
    print(f"📂 발견된 파일: {len(input_files)}개\n")
    
    # PDF 처리 및 JSON 저장
    print("=" * 60)
    print("🚀 PDF 처리 및 JSON 변환 시작")
    print("=" * 60)

    for i, input_file in enumerate(input_files, 1):
        filename = input_file.name
        print(f"\n[{i}/{len(input_files)}] 📄 {filename}")
        
        try:
            chunks = process_file(
                str(input_file),
                text_splitter,
                args.page_offset,
                args.double_page,
                args.auto_detect,
            )
            
            if chunks:
                # 출력 파일명 결정 (입력 파일명 유지)
                output_filename = input_file.stem + ".json"
                output_file = output_dir / output_filename
                
                # 메타데이터 정제 (None 제거)
                for chunk in chunks:
                    clean_meta = {
                        k: (v if v is not None else "")
                        for k, v in chunk['metadata'].items()
                    }
                    chunk['metadata'] = clean_meta

                # JSON 저장
                with open(output_file, 'w', encoding='utf-8') as f:
                    # DB Builder가 기대하는 포맷: list of dicts, or dict with 'chunks' list
                    # 여기서는 list of dicts로 저장
                    f.write(json.dumps(chunks, ensure_ascii=False, indent=2))
                
            if chunks:
                # ...
                print(f"   💾 저장 완료: {output_filename}")
                print(f"   📊 청크 수: {len(chunks):,}개")
            else:
                print(f"   ⚠️  생성된 청크가 없습니다. (빈 파일 또는 OCR 필요)")
                sys.exit(1) # 파이프라인에 실패 알림

        except Exception as e:
            print(f"      ❌ 오류: {e}")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 변환 완료!")
    
    print("\n" + "=" * 60)
    print("🎉 완료!")
    print("=" * 60)
    print(f"\n다음 단계:")
    print(f"  cd .")
    print(f"  source venv.nosync/bin/activate")
    print(f"  python db_builder.py")


if __name__ == "__main__":
    main()
