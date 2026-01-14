#!/usr/bin/env python3
"""
PDF 페이지 번호 자동 감지 (OCR 기반)

종이책의 실제 페이지 번호를 PDF에서 자동으로 추출하여
pdf_page → print_page 매핑 테이블 생성

지원하는 페이지 번호 형식:
- 아라비아 숫자: 1, 2, 3, ...
- 로마 숫자: i, ii, iii, iv, v, vi, vii, viii, ix, x, xi, xii, ...
- 빈 페이지 (번호 없음)

사용법:
    from page_number_detector import PageNumberDetector

    detector = PageNumberDetector()
    mapping = detector.detect_page_numbers("book.pdf")
    # mapping = {1: None, 2: "i", 3: "ii", ..., 15: 1, 16: 2, ...}
"""

import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Union
from dataclasses import dataclass
from enum import Enum

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    pytesseract = None
    convert_from_path = None


class PageNumberType(Enum):
    """페이지 번호 유형"""
    ARABIC = "arabic"      # 1, 2, 3, ...
    ROMAN = "roman"        # i, ii, iii, ...
    NONE = "none"          # 페이지 번호 없음


@dataclass
class PageInfo:
    """페이지 정보"""
    pdf_page: int                           # PDF 물리적 페이지 (1-based)
    print_page: Optional[Union[int, str]]   # 인쇄본 페이지 번호 (또는 로마숫자 문자열)
    page_type: PageNumberType               # 페이지 번호 유형
    confidence: float                       # 감지 신뢰도 (0.0 ~ 1.0)
    raw_text: str = ""                      # OCR로 추출한 원본 텍스트


class PageNumberDetector:
    """PDF 페이지 번호 자동 감지기"""

    # 로마숫자 매핑
    ROMAN_VALUES = {
        'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
        'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10,
        'xi': 11, 'xii': 12, 'xiii': 13, 'xiv': 14, 'xv': 15,
        'xvi': 16, 'xvii': 17, 'xviii': 18, 'xix': 19, 'xx': 20,
        'xxi': 21, 'xxii': 22, 'xxiii': 23, 'xxiv': 24, 'xxv': 25,
        'xxvi': 26, 'xxvii': 27, 'xxviii': 28, 'xxix': 29, 'xxx': 30,
    }

    # 아라비아 숫자 패턴 (페이지 번호로 적합한 위치)
    # 순서 중요: 더 엄격한 패턴 먼저
    ARABIC_PATTERNS = [
        r'^\s*(\d{1,3})\s*$',                    # 단독 숫자 (1-3자리만)
        r'[-–—]\s*(\d{1,3})\s*[-–—]',            # 대시로 감싼 숫자
    ]

    # 제외할 숫자 패턴 (페이지 번호가 아닌 것들)
    EXCLUDE_PATTERNS = [
        r'19\d{2}',  # 연도 (1900년대)
        r'20\d{2}',  # 연도 (2000년대)
        r'ISBN',     # ISBN 관련
        r'pp?\.\s*\d+',  # 참조 페이지
    ]

    # 로마숫자 패턴
    ROMAN_PATTERNS = [
        r'^\s*(x{0,3}(?:ix|iv|v?i{0,3}))\s*$',  # 단독 로마숫자
        r'[-–—]\s*(x{0,3}(?:ix|iv|v?i{0,3}))\s*[-–—]',  # 대시로 감싼 로마숫자
    ]

    def __init__(self, ocr_lang: str = "eng+deu"):
        """
        Args:
            ocr_lang: Tesseract 언어 설정 (기본: 영어+독일어)
        """
        self.ocr_lang = ocr_lang
        self._check_dependencies()

    def _check_dependencies(self):
        """의존성 확인"""
        if not PdfReader:
            raise ImportError("pypdf 패키지가 필요합니다: pip install pypdf")
        if not OCR_AVAILABLE:
            print("⚠️ OCR 의존성 없음 (pytesseract, pdf2image). 텍스트 추출만 사용합니다.")

    def detect_page_numbers(
        self,
        pdf_path: str,
        sample_pages: int = 20,
        use_ocr: bool = True,
    ) -> Dict[int, PageInfo]:
        """
        PDF에서 페이지 번호 자동 감지

        Args:
            pdf_path: PDF 파일 경로
            sample_pages: 샘플링할 페이지 수 (처음 N페이지)
            use_ocr: OCR 사용 여부 (텍스트 추출 실패 시)

        Returns:
            {pdf_page: PageInfo} 매핑
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {pdf_path}")

        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        print(f"📖 {path.name} ({total_pages}페이지)")
        print(f"   샘플링: 처음 {min(sample_pages, total_pages)}페이지")

        results: Dict[int, PageInfo] = {}

        # 1단계: 텍스트 추출로 페이지 번호 감지
        for pdf_page in range(1, min(sample_pages, total_pages) + 1):
            page = reader.pages[pdf_page - 1]
            text = page.extract_text() or ""

            page_info = self._detect_from_text(pdf_page, text)

            # 텍스트 추출 실패 시 OCR 시도
            if page_info.page_type == PageNumberType.NONE and use_ocr and OCR_AVAILABLE:
                page_info = self._detect_from_ocr(pdf_path, pdf_page)

            results[pdf_page] = page_info

        # 2단계: 패턴 분석 및 보정
        results = self._analyze_and_correct(results)

        # 3단계: 전체 페이지로 확장 (패턴 기반)
        results = self._extend_to_all_pages(results, total_pages)

        # 통계 출력
        self._print_statistics(results)

        return results

    def _detect_from_text(self, pdf_page: int, text: str) -> PageInfo:
        """텍스트에서 페이지 번호 감지"""
        # 페이지 하단/상단 영역 추출 (페이지 번호가 주로 위치하는 곳)
        lines = text.strip().split('\n')

        # 상단 3줄 + 하단 3줄 검사
        check_lines = lines[:3] + lines[-3:] if len(lines) > 6 else lines

        for line in check_lines:
            line = line.strip()
            if not line:
                continue

            # 제외 패턴 체크
            should_exclude = any(re.search(ep, line) for ep in self.EXCLUDE_PATTERNS)
            if should_exclude:
                continue

            # 아라비아 숫자 검사
            for pattern in self.ARABIC_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    num = int(match.group(1))
                    # 페이지 번호로 적합한 범위 (1-999)
                    if 1 <= num <= 999:
                        return PageInfo(
                            pdf_page=pdf_page,
                            print_page=num,
                            page_type=PageNumberType.ARABIC,
                            confidence=0.8,
                            raw_text=line
                        )

            # 로마숫자 검사
            for pattern in self.ROMAN_PATTERNS:
                match = re.search(pattern, line.lower())
                if match:
                    roman = match.group(1).lower()
                    if roman in self.ROMAN_VALUES:
                        return PageInfo(
                            pdf_page=pdf_page,
                            print_page=roman,
                            page_type=PageNumberType.ROMAN,
                            confidence=0.7,
                            raw_text=line
                        )

        return PageInfo(
            pdf_page=pdf_page,
            print_page=None,
            page_type=PageNumberType.NONE,
            confidence=0.0
        )

    def _detect_from_ocr(self, pdf_path: str, pdf_page: int) -> PageInfo:
        """OCR로 페이지 번호 감지 (하단/상단 영역만)"""
        if not OCR_AVAILABLE:
            return PageInfo(
                pdf_page=pdf_page,
                print_page=None,
                page_type=PageNumberType.NONE,
                confidence=0.0
            )

        try:
            # PDF 페이지를 이미지로 변환 (해당 페이지만)
            images = convert_from_path(
                pdf_path,
                first_page=pdf_page,
                last_page=pdf_page,
                dpi=150  # 속도를 위해 낮은 DPI
            )

            if not images:
                return PageInfo(
                    pdf_page=pdf_page,
                    print_page=None,
                    page_type=PageNumberType.NONE,
                    confidence=0.0
                )

            img = images[0]
            width, height = img.size

            # 상단 10% + 하단 10% 영역만 OCR
            regions = [
                img.crop((0, 0, width, int(height * 0.1))),           # 상단
                img.crop((0, int(height * 0.9), width, height)),     # 하단
            ]

            for region in regions:
                text = pytesseract.image_to_string(region, lang=self.ocr_lang)
                result = self._detect_from_text(pdf_page, text)
                if result.page_type != PageNumberType.NONE:
                    result.confidence *= 0.9  # OCR은 신뢰도 약간 낮춤
                    return result

        except Exception as e:
            print(f"      ⚠️ OCR 오류 (p.{pdf_page}): {e}")

        return PageInfo(
            pdf_page=pdf_page,
            print_page=None,
            page_type=PageNumberType.NONE,
            confidence=0.0
        )

    def _analyze_and_correct(self, results: Dict[int, PageInfo]) -> Dict[int, PageInfo]:
        """패턴 분석 및 이상치 보정"""
        # 연속성 검사: 페이지 번호가 순차적으로 증가하는지
        sorted_pages = sorted(results.keys())

        # 아라비아 숫자 페이지들의 연속성 검사
        arabic_pages = [
            (p, results[p].print_page)
            for p in sorted_pages
            if results[p].page_type == PageNumberType.ARABIC
        ]

        if len(arabic_pages) >= 3:
            # 오프셋 계산 (pdf_page - print_page)
            offsets = [pdf - print_p for pdf, print_p in arabic_pages if print_p]
            if offsets:
                # 가장 빈번한 오프셋 찾기
                from collections import Counter
                offset_counts = Counter(offsets)
                most_common_offset = offset_counts.most_common(1)[0][0]

                # 이상치 보정
                for pdf_page in sorted_pages:
                    info = results[pdf_page]
                    if info.page_type == PageNumberType.ARABIC:
                        expected = pdf_page - most_common_offset
                        if info.print_page != expected and abs(info.print_page - expected) <= 2:
                            # 오차가 2 이내면 보정
                            info.print_page = expected
                            info.confidence = 0.6

        return results

    def _extend_to_all_pages(
        self,
        results: Dict[int, PageInfo],
        total_pages: int
    ) -> Dict[int, PageInfo]:
        """샘플 결과를 전체 페이지로 확장"""
        # 오프셋 계산
        arabic_pages = [
            (p, info.print_page)
            for p, info in results.items()
            if info.page_type == PageNumberType.ARABIC and info.print_page
        ]

        if not arabic_pages:
            # 아라비아 숫자 페이지가 없으면 확장 불가
            return results

        # 평균 오프셋 계산
        offsets = [pdf - print_p for pdf, print_p in arabic_pages]
        avg_offset = round(sum(offsets) / len(offsets))

        # 본문 시작 페이지 찾기 (아라비아 숫자가 시작되는 PDF 페이지)
        first_arabic_pdf = min(p for p, _ in arabic_pages)

        # 전체 페이지 확장
        for pdf_page in range(1, total_pages + 1):
            if pdf_page not in results:
                if pdf_page >= first_arabic_pdf:
                    # 본문 영역: 아라비아 숫자
                    results[pdf_page] = PageInfo(
                        pdf_page=pdf_page,
                        print_page=pdf_page - avg_offset,
                        page_type=PageNumberType.ARABIC,
                        confidence=0.5  # 추정값
                    )
                else:
                    # 앞부분: 로마숫자 또는 없음
                    results[pdf_page] = PageInfo(
                        pdf_page=pdf_page,
                        print_page=None,
                        page_type=PageNumberType.NONE,
                        confidence=0.3
                    )

        return results

    def _print_statistics(self, results: Dict[int, PageInfo]):
        """통계 출력"""
        total = len(results)
        arabic = sum(1 for r in results.values() if r.page_type == PageNumberType.ARABIC)
        roman = sum(1 for r in results.values() if r.page_type == PageNumberType.ROMAN)
        none_type = sum(1 for r in results.values() if r.page_type == PageNumberType.NONE)

        avg_conf = sum(r.confidence for r in results.values()) / total if total else 0

        print(f"\n   📊 감지 결과:")
        print(f"      - 아라비아: {arabic}페이지")
        print(f"      - 로마숫자: {roman}페이지")
        print(f"      - 미감지: {none_type}페이지")
        print(f"      - 평균 신뢰도: {avg_conf:.1%}")

        # 오프셋 정보
        arabic_pages = [
            (p, r.print_page)
            for p, r in results.items()
            if r.page_type == PageNumberType.ARABIC and r.print_page
        ]
        if arabic_pages:
            first_pdf, first_print = min(arabic_pages, key=lambda x: x[0])
            print(f"      - 본문 시작: PDF p.{first_pdf} = 종이 p.{first_print}")
            print(f"      - 오프셋: {first_pdf - first_print}")

    def get_print_page(
        self,
        results: Dict[int, PageInfo],
        pdf_page: int
    ) -> Optional[int]:
        """PDF 페이지에 해당하는 종이책 페이지 반환"""
        if pdf_page not in results:
            return None

        info = results[pdf_page]
        if info.page_type == PageNumberType.ARABIC:
            return info.print_page
        elif info.page_type == PageNumberType.ROMAN:
            # 로마숫자는 음수로 변환 (정렬/검색 용이)
            return -self.ROMAN_VALUES.get(info.print_page, 0)
        else:
            return None

    def create_offset_map(self, results: Dict[int, PageInfo]) -> Dict[int, int]:
        """
        pdf_page → print_page 단순 매핑 생성
        (local_pdf_processor와 호환)
        """
        mapping = {}
        for pdf_page, info in results.items():
            if info.page_type == PageNumberType.ARABIC and info.print_page:
                mapping[pdf_page] = info.print_page
        return mapping


# ═══════════════════════════════════════════════════════════════════
# CLI 실행
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description='PDF 페이지 번호 자동 감지'
    )
    parser.add_argument('pdf', help='PDF 파일 경로')
    parser.add_argument('--sample', type=int, default=30,
                        help='샘플링할 페이지 수 (기본: 30)')
    parser.add_argument('--no-ocr', action='store_true',
                        help='OCR 사용 안 함 (텍스트 추출만)')
    parser.add_argument('--output', '-o', help='결과 JSON 저장 경로')
    parser.add_argument('--lang', default='eng+deu',
                        help='OCR 언어 (기본: eng+deu)')

    args = parser.parse_args()

    print("=" * 60)
    print("📖 PDF 페이지 번호 자동 감지")
    print("=" * 60)

    detector = PageNumberDetector(ocr_lang=args.lang)
    results = detector.detect_page_numbers(
        args.pdf,
        sample_pages=args.sample,
        use_ocr=not args.no_ocr
    )

    # 결과 출력
    print("\n" + "=" * 60)
    print("📋 페이지 매핑 (처음 20개)")
    print("=" * 60)

    for pdf_page in sorted(results.keys())[:20]:
        info = results[pdf_page]
        print_p = info.print_page if info.print_page else "—"
        conf = f"({info.confidence:.0%})" if info.confidence > 0 else ""
        print(f"   PDF {pdf_page:3d} → 종이 {str(print_p):>5s} {conf}")

    # JSON 저장
    if args.output:
        output_data = {
            str(k): {
                "pdf_page": v.pdf_page,
                "print_page": v.print_page,
                "type": v.page_type.value,
                "confidence": v.confidence
            }
            for k, v in results.items()
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 저장 완료: {args.output}")


if __name__ == "__main__":
    main()
