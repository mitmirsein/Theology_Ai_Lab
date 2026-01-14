#!/usr/bin/env python3
"""
페이지 매핑 템플릿 로더 (v2.1)

PDF와 함께 .mapping.json 파일을 두면 자동으로 페이지 매핑 적용.
AI 없이 사용자가 직접 매핑 파일을 작성하여 정확한 페이지 번호 지정.

사용법:
    1. PDF 파일과 같은 이름의 .mapping.json 파일 생성
       예: TRE_Bd4.pdf → TRE_Bd4.mapping.json

    2. 매핑 파일 작성 (samples 방식 권장)

    3. local_pdf_processor.py 실행 시 자동 적용

매핑 파일 형식:
    - samples: 샘플 지점 기반 보간 (권장)
    - offset: 단순 오프셋
    - full: 전체 페이지 명시적 매핑
"""

import json
from pathlib import Path
from typing import Dict, Optional, List, Any, Union
from dataclasses import dataclass


@dataclass
class MappingResult:
    """매핑 결과"""
    page_map: Dict[int, Optional[int]]  # pdf_page → print_page (None = 도판 등)
    offset: Optional[int]               # 계산된 기본 오프셋
    has_irregulars: bool                # 불규칙 구간 존재 여부
    info: str                           # 매핑 정보 요약


def load_mapping_file(pdf_path: str) -> Optional[MappingResult]:
    """
    PDF에 해당하는 매핑 파일 로드

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        MappingResult 또는 None (매핑 파일 없을 시)
    """
    pdf_path = Path(pdf_path)
    mapping_path = pdf_path.with_suffix('.mapping.json')

    if not mapping_path.exists():
        return None

    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"      ⚠️ 매핑 파일 오류: {e}")
        return None

    mapping_type = data.get('type', 'samples')

    if mapping_type == 'samples':
        return _process_samples_mapping(data, pdf_path.name)
    elif mapping_type == 'offset':
        return _process_offset_mapping(data, pdf_path.name)
    elif mapping_type == 'full':
        return _process_full_mapping(data, pdf_path.name)
    else:
        print(f"      ⚠️ 알 수 없는 매핑 타입: {mapping_type}")
        return None


def _process_samples_mapping(data: dict, filename: str) -> MappingResult:
    """
    샘플 기반 매핑 처리

    샘플 간 선형 보간으로 전체 페이지 매핑 생성
    """
    samples = data.get('samples', [])
    if not samples:
        return MappingResult({}, None, False, "샘플 없음")

    # 샘플 정렬 (PDF 페이지 기준)
    samples = sorted(samples, key=lambda x: x['pdf'])

    page_map: Dict[int, Optional[int]] = {}
    irregulars: List[int] = []  # 불규칙 페이지 (도판 등)

    # 유효한 샘플만 추출 (print가 숫자인 것)
    valid_samples = [
        s for s in samples
        if s.get('print') is not None and isinstance(s.get('print'), (int, float))
    ]

    # 오프셋 계산 (첫 번째 유효 샘플 기준)
    base_offset = None
    if valid_samples:
        first = valid_samples[0]
        base_offset = first['pdf'] - first['print']

    # 불규칙 페이지 먼저 처리
    for sample in samples:
        pdf_page = sample['pdf']
        print_page = sample.get('print')

        if print_page is None:
            # 도판, 빈 페이지 등
            page_map[pdf_page] = None
            irregulars.append(pdf_page)

    # 샘플 간 보간
    for i in range(len(valid_samples)):
        current = valid_samples[i]
        pdf_curr = current['pdf']
        print_curr = current['print']

        # 현재 샘플 추가
        page_map[pdf_curr] = int(print_curr)

        # 다음 샘플까지 보간
        if i + 1 < len(valid_samples):
            next_sample = valid_samples[i + 1]
            pdf_next = next_sample['pdf']
            print_next = next_sample['print']

            # 두 샘플 간 오프셋이 동일한지 확인
            offset_curr = pdf_curr - print_curr
            offset_next = pdf_next - print_next

            if offset_curr == offset_next:
                # 오프셋 일관: 선형 보간
                for pdf_p in range(pdf_curr + 1, pdf_next):
                    if pdf_p not in irregulars:
                        page_map[pdf_p] = pdf_p - int(offset_curr)
            else:
                # 오프셋 불일치: 불규칙 구간 존재
                # 가능한 범위만 추정 (앞 샘플 오프셋 적용)
                for pdf_p in range(pdf_curr + 1, pdf_next):
                    if pdf_p not in irregulars:
                        page_map[pdf_p] = pdf_p - int(offset_curr)

    # 마지막 샘플 이후 확장 (오프셋 유지)
    if valid_samples:
        last = valid_samples[-1]
        last_offset = last['pdf'] - last['print']
        # 마지막 샘플 이후 100페이지까지 확장 (필요 시)
        max_page = data.get('total_pages', last['pdf'] + 100)
        for pdf_p in range(last['pdf'] + 1, max_page + 1):
            if pdf_p not in page_map:
                page_map[pdf_p] = pdf_p - int(last_offset)

    # 첫 샘플 이전 처리 (print=None 또는 음수 방지)
    if valid_samples:
        first = valid_samples[0]
        first_offset = first['pdf'] - first['print']
        for pdf_p in range(1, first['pdf']):
            if pdf_p not in page_map:
                calc_print = pdf_p - int(first_offset)
                page_map[pdf_p] = calc_print if calc_print > 0 else None

    info = f"샘플 {len(samples)}개, 오프셋 {base_offset}, 불규칙 {len(irregulars)}개"
    return MappingResult(page_map, base_offset, len(irregulars) > 0, info)


def _process_offset_mapping(data: dict, filename: str) -> MappingResult:
    """단순 오프셋 매핑"""
    offset = data.get('offset', 0)
    total_pages = data.get('total_pages', 500)

    page_map = {}
    for pdf_p in range(1, total_pages + 1):
        print_p = pdf_p - offset
        page_map[pdf_p] = print_p if print_p > 0 else None

    return MappingResult(page_map, offset, False, f"오프셋 {offset}")


def _process_full_mapping(data: dict, filename: str) -> MappingResult:
    """전체 페이지 명시적 매핑"""
    pages = data.get('pages', {})

    page_map = {}
    for pdf_str, print_val in pages.items():
        try:
            pdf_p = int(pdf_str)
            page_map[pdf_p] = int(print_val) if print_val else None
        except (ValueError, TypeError):
            continue

    # 오프셋 추정
    offsets = [pdf - print_p for pdf, print_p in page_map.items() if print_p]
    avg_offset = round(sum(offsets) / len(offsets)) if offsets else None

    return MappingResult(page_map, avg_offset, False, f"명시적 매핑 {len(page_map)}페이지")


def create_template(pdf_path: str, total_pages: int = None) -> str:
    """
    빈 매핑 템플릿 생성

    Args:
        pdf_path: PDF 파일 경로
        total_pages: 총 페이지 수 (선택)

    Returns:
        생성된 템플릿 파일 경로
    """
    pdf_path = Path(pdf_path)
    mapping_path = pdf_path.with_suffix('.mapping.json')

    template = {
        "_comment": "페이지 매핑 템플릿 - PDF를 보면서 샘플 지점 입력",
        "_usage": [
            "pdf: PDF 뷰어에서 보이는 페이지 번호",
            "print: 해당 페이지에 인쇄된 페이지 번호 (없으면 null)",
            "note: 메모 (선택사항)"
        ],
        "type": "samples",
        "total_pages": total_pages,
        "samples": [
            {"pdf": 1, "print": None, "note": "표지"},
            {"pdf": 5, "print": None, "note": "목차 또는 서문 (로마숫자)"},
            {"pdf": 10, "print": None, "note": "서문 끝"},
            {"pdf": 15, "print": 1, "note": "본문 시작 ← 여기 수정"},
            {"pdf": 50, "print": 36, "note": "중간 확인"},
            {"pdf": 100, "print": 86, "note": "중간 확인 2"},
            {"pdf": 150, "print": None, "note": "도판 페이지 (있다면)"},
            {"pdf": 151, "print": 136, "note": "도판 이후"},
            {"pdf": 200, "print": 186, "note": "후반부"},
            {"pdf": 300, "print": 286, "note": "끝부분"}
        ]
    }

    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    return str(mapping_path)


def get_print_page(mapping: MappingResult, pdf_page: int) -> Optional[int]:
    """매핑에서 인쇄본 페이지 조회"""
    if not mapping:
        return None
    return mapping.page_map.get(pdf_page)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='페이지 매핑 템플릿 도구'
    )
    subparsers = parser.add_subparsers(dest='command', help='명령어')

    # create: 템플릿 생성
    create_parser = subparsers.add_parser('create', help='빈 템플릿 생성')
    create_parser.add_argument('pdf', help='PDF 파일 경로')
    create_parser.add_argument('--pages', type=int, help='총 페이지 수')

    # test: 매핑 테스트
    test_parser = subparsers.add_parser('test', help='매핑 파일 테스트')
    test_parser.add_argument('pdf', help='PDF 파일 경로')
    test_parser.add_argument('--page', type=int, help='특정 PDF 페이지 조회')

    args = parser.parse_args()

    if args.command == 'create':
        path = create_template(args.pdf, args.pages)
        print(f"✅ 템플릿 생성: {path}")
        print("\nPDF를 열고 샘플 지점의 페이지 번호를 확인하여 수정하세요.")

    elif args.command == 'test':
        result = load_mapping_file(args.pdf)
        if not result:
            print("❌ 매핑 파일을 찾을 수 없습니다.")
            return

        print(f"📖 매핑 정보: {result.info}")
        print(f"   기본 오프셋: {result.offset}")
        print(f"   불규칙 구간: {'있음' if result.has_irregulars else '없음'}")

        if args.page:
            print_p = get_print_page(result, args.page)
            if print_p is None:
                print(f"\n   PDF {args.page} → 종이 페이지 없음 (도판/빈 페이지)")
            else:
                print(f"\n   PDF {args.page} → 종이 {print_p}")
        else:
            print("\n📋 처음 20페이지 매핑:")
            for pdf_p in sorted(result.page_map.keys())[:20]:
                print_p = result.page_map[pdf_p]
                print_str = str(print_p) if print_p else "—"
                print(f"   PDF {pdf_p:3d} → 종이 {print_str:>4s}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
