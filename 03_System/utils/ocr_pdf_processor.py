#!/usr/bin/env python3
"""
OCR 통합 PDF 프로세서
자동으로 OCR 필요 여부를 감지하고 처리

Requirements:
  brew install tesseract tesseract-lang poppler
  pip install pytesseract pdf2image pillow
"""

import os
import sys
from pathlib import Path

# Mac MacPorts poppler를 PATH에 추가 (Homebrew 대신)
os.environ['PATH'] = '/opt/local/bin:' + os.environ.get('PATH', '')

# OCR 라이브러리 체크
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from pypdf import PdfReader


def check_pdf_has_text(pdf_path: str, sample_pages: int = 3) -> bool:
    """
    PDF가 텍스트를 포함하는지 확인
    
    Args:
        pdf_path: PDF 파일 경로
        sample_pages: 확인할 페이지 수
    
    Returns:
        True: 텍스트 있음 (OCR 불필요)
        False: 이미지만 있음 (OCR 필요)
    """
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        check_pages = min(sample_pages, total_pages)
        
        total_chars = 0
        for i in range(check_pages):
            text = reader.pages[i].extract_text() or ""
            total_chars += len(text.strip())
        
        # 페이지당 평균 50자 이상이면 텍스트 있음으로 간주
        avg_chars_per_page = total_chars / check_pages
        
        return avg_chars_per_page > 50
    
    except Exception as e:
        print(f"⚠️  PDF 확인 오류: {e}")
        return False


import re

def clean_ocr_text(text: str) -> str:
    """OCR 결과에서 불필요한 워터마크 및 메타데이터 제거"""
    patterns = [
        r"Digitized by Google",
        r"Original from UNIVERSITY OF MICHIGAN",
        r"http://books.google.com",
        r"Google", # 단독 Google 워터마크 포함
    ]
    cleaned_text = text
    for p in patterns:
        cleaned_text = re.sub(p, "", cleaned_text, flags=re.IGNORECASE)
    
    # 중복 공백 및 줄바꿈 정리
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    return cleaned_text.strip()


def ocr_images(image_paths: list, output_path: str = None, languages: str = 'deu+eng+grc+heb') -> str:
    """
    여러 이미지 파일을 순차적으로 OCR 처리.
    """
    print(f"   🔍 이미지 OCR 처리 중... (언어: {languages}, 총: {len(image_paths)} 파일)")
    
    full_text = ""
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"--- 이미지 집합 OCR 처리 시작 (총 {len(image_paths)}개) ---\n\n")

    try:
        for i, img_path in enumerate(image_paths, 1):
            try:
                image = Image.open(img_path)
                page_text = pytesseract.image_to_string(image, lang=languages, config='--psm 1')
                cleaned_page_text = clean_ocr_text(page_text)
                
                page_output = f"\n\n--- Image: {os.path.basename(img_path)} (Page {i}) ---\n\n"
                page_output += cleaned_page_text
                full_text += page_output
                
                if output_path:
                    with open(output_path, 'a', encoding='utf-8') as f:
                        f.write(page_output)
                
                if i % 10 == 0 or i == len(image_paths):
                    print(f"      진행: {i}/{len(image_paths)} 파일 완료")
            except Exception as e:
                print(f"      ⚠️  이미지 {img_path} OCR 오류: {e}")
                continue
        
        return full_text
    except Exception as e:
        raise RuntimeError(f"이미지 OCR 처리 실패: {e}")

def ocr_pdf(pdf_path: str, output_path: str = None, languages: str = 'deu+eng+grc+heb', batch_size: int = 10) -> str:
    """
    PDF를 배치 단위로 OCR 처리하여 속도와 메모리 점유의 균형을 맞춤.
    결과를 즉시 파일에 저장하여 프로세스 중단 시에도 데이터 보존.
    
    Args:
        pdf_path: PDF 파일 경로
        output_path: 텍스트 저장 경로
        languages: Tesseract 언어 코드
        batch_size: 한 번에 처리할 페이지 수 (기본: 10)
    """
    if not OCR_AVAILABLE:
        raise ImportError(
            "OCR 라이브러리가 설치되지 않았습니다.\n"
            "다음 명령을 실행하세요:\n"
            "  brew install tesseract tesseract-lang poppler\n"
            "  pip install pytesseract pdf2image pillow"
        )
    
    # 페이지 수 확인
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
    except Exception as e:
        print(f"⚠️  PDF 페이지 수를 확인할 수 없습니다: {e}")
        total_pages = 0 
    
    print(f"   🔍 OCR 처리 중... (언어: {languages}, 총: {total_pages} 페이지, 배치: {batch_size})")
    
    full_text = ""
    
    # 출력 파일 초기화
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"--- OCR 처리 시작: {pdf_path} (배치 사이즈: {batch_size}) ---\n\n")

    try:
        # 배치 단위 처리
        for start_page in range(1, total_pages + 1, batch_size):
            end_page = min(start_page + batch_size - 1, total_pages)
            try:
                # 배치 범위의 이미지를 한꺼번에 변환 (PDF 오픈 오버헤드 감소)
                images = convert_from_path(
                    pdf_path, 
                    dpi=300, 
                    first_page=start_page, 
                    last_page=end_page
                )
                
                if not images:
                    continue
                
                batch_output = ""
                for j, image in enumerate(images):
                    current_page = start_page + j
                    
                    # Tesseract OCR
                    page_text = pytesseract.image_to_string(
                        image,
                        lang=languages,
                        config='--psm 1'
                    )
                    
                    # 워터마크 제거
                    cleaned_page_text = clean_ocr_text(page_text)
                    
                    page_output = f"\n\n--- Page {current_page} ---\n\n"
                    page_output += cleaned_page_text
                    batch_output += page_output
                
                full_text += batch_output
                
                # 배치 단위로 즉시 파일에 추가
                if output_path:
                    with open(output_path, 'a', encoding='utf-8') as f:
                        f.write(batch_output)
                
                print(f"      진행: {end_page}/{total_pages} 페이지 완료")
                
                # 메모리 해제
                del images
                    
            except Exception as e:
                print(f"      ⚠️  페이지 {start_page}-{end_page} 배치 OCR 오류: {e}")
                continue
        
        print(f"      ✅ OCR 완료 ({len(full_text):,}자 추출)")
        return full_text
    
    except Exception as e:
        raise RuntimeError(f"OCR 처리 실패: {e}")


def save_ocr_text(text: str, output_path: str):
    """OCR 결과를 텍스트 파일로 저장"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    file_size = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"      💾 OCR 결과 저장: {output_path} ({file_size:.1f}MB)")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='PDF OCR 처리 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 자동 감지 및 OCR
  python ocr_pdf_processor.py input.pdf
  
  # 강제 OCR
  python ocr_pdf_processor.py input.pdf --force
  
  # 출력 경로 지정
  python ocr_pdf_processor.py input.pdf -o output.txt
  
  # 언어 지정 (독일어만)
  python ocr_pdf_processor.py input.pdf --lang deu
        """
    )
    
    parser.add_argument('input', help='PDF 파일 경로')
    parser.add_argument('-o', '--output', help='출력 파일 경로 (기본: input_ocr.txt)')
    parser.add_argument('--force', action='store_true', 
                        help='텍스트가 있어도 강제로 OCR 실행')
    parser.add_argument('--lang', default='deu+eng+grc+heb',
                        help='Tesseract 언어 코드 (기본: deu+eng+grc+heb)')
    parser.add_argument('--batch-size', type=int, default=10,
                        help='한 번에 처리할 페이지 수 (기본: 10, 메모리 상황에 따라 조절)')
    parser.add_argument('--check-only', action='store_true',
                        help='OCR 필요 여부만 확인')
    
    args = parser.parse_args()
    
    # 입력 확인 및 경로 정규화 (이미지 폴더 지원)
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 경로를 찾을 수 없습니다: {args.input}")
        sys.exit(1)
    
    # 출력 파일 경로 미리 결정
    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.with_name(f"{input_path.stem}_ocr.txt"))

    # 이미지 폴더 여부 확인
    if input_path.is_dir():
        print(f"📂 폴더 입력 감지: {args.input}")
        # 이미지 파일 확장자 필터링 (.png, .jpg, .jpeg)
        image_extensions = ['.png', '.jpg', '.jpeg']
        image_files = sorted(
            [f for f in input_path.iterdir() if f.suffix.lower() in image_extensions],
            key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x.name)] # 숫자 기반 자연 정렬
        )
        
        if not image_files:
            print("❌ 폴더 내에 이미지 파일(.png, .jpg, .jpeg)이 없습니다.")
            sys.exit(1)
            
        try:
            ocr_images(image_files, output_path=output_path, languages=args.lang)
            print(f"\n✅ 이미지 폴더 OCR 완료! 결과: {output_path}")
        except Exception as e:
            print(f"\n❌ OCR 실패: {e}")
            sys.exit(1)
            
    else:
        # 기존 PDF 처리 로직
        # OCR 필요 여부 확인
        has_text = check_pdf_has_text(args.input)
        
        if args.check_only:
            if has_text:
                print("✅ 텍스트 포함된 PDF (OCR 불필요)")
            else:
                print("❌ 이미지 기반 PDF (OCR 필요)")
            sys.exit(0)
        
        if has_text and not args.force:
            print("✅ 텍스트가 포함된 PDF입니다. --force 옵션 없이 중단합니다.")
            sys.exit(0)
            
        try:
            text = ocr_pdf(
                args.input, 
                output_path=output_path, 
                languages=args.lang,
                batch_size=args.batch_size
            )
            print(f"\n✅ PDF OCR 완료! 결과: {output_path}")
        except Exception as e:
            print(f"\n❌ OCR 실패: {e}")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 OCR 작업 종료")
    print("=" * 60)


if __name__ == "__main__":
    main()
