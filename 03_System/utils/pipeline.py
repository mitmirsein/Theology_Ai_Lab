#!/usr/bin/env python3
"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  pipeline.py — Theology AI Lab 통합 처리 파이프라인                    ┃
┃                                                                       ┃
┃  기능:                                                                ┃
┃    1. OCR 필요 여부 자동 감지                                          ┃
┃    2. OCR 실행 (이미지 PDF인 경우)                                     ┃
┃    3. 청킹 및 메타데이터 추출                                          ┃
┃    4. ChromaDB 인덱싱                                                 ┃
┃    5. Lemma 인덱스 업데이트                                           ┃
┃                                                                       ┃
┃  Usage:                                                               ┃
┃    python pipeline.py                     # inbox 전체 처리            ┃
┃    python pipeline.py /path/to/file.pdf   # 단일 파일 처리             ┃
┃                                                                       ┃
┃  Version: 2.0.0                                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""

import os
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# 로깅 설정
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """통합 처리 파이프라인"""

    def __init__(self):
        # 스크립트 경로 (Docker 환경 고려)
        self.script_dir = Path(__file__).parent.absolute()
        self.tools_dir = self.script_dir.parent / "tools"
        
        # [v2.7.23] kit_root 기반 경로 (db_builder.py와 동일한 방식)
        # utils -> 03_System -> Theology_AI_Lab (Root)
        self.kit_root = self.script_dir.parent.parent
        
        # 환경 변수에서 경로 로드 (상대 경로일 경우 kit_root 기준으로 해석)
        def resolve_path(env_var: str, default_rel: str) -> Path:
            env_val = os.getenv(env_var)
            if env_val:
                if env_val.startswith("."):
                    return self.kit_root / env_val
                return Path(env_val)
            return self.kit_root / default_rel
        
        self.inbox_dir = resolve_path("INBOX_DIR", "01_Library/inbox")
        self.archive_dir = resolve_path("ARCHIVE_DIR", "01_Library/archive")
        self.db_dir = resolve_path("CHROMA_DB_DIR", "02_Brain/vector_db")
        
        logger.info(f"📂 Kit Root: {self.kit_root}")
        logger.info(f"📂 Inbox: {self.inbox_dir}")

        # OCR 설정
        self.ocr_enabled = os.getenv("OCR_ENABLED", "true").lower() == "true"
        self.ocr_languages = os.getenv("OCR_LANGUAGES", "deu+eng+grc+heb+kor")

        # [v2.1] 가상환경 Python 탐지
        self.python_exe = sys.executable
        venv_python = self.script_dir.parent / "venv" / "bin" / "python3"
        if not venv_python.exists():
            venv_python = self.script_dir.parent / "venv" / "Scripts" / "python.exe"
            
        if venv_python.exists():
            self.python_exe = str(venv_python)
            logger.info(f"🐍 가상환경 Python 사용: {self.python_exe}")

    def check_needs_ocr(self, file_path: Path) -> bool:
        """
        PDF가 OCR이 필요한지 확인

        Args:
            file_path: PDF 파일 경로

        Returns:
            True: OCR 필요 (이미지 PDF)
            False: OCR 불필요 (텍스트 포함)
        """
        if file_path.suffix.lower() != ".pdf":
            return False

        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)
            check_pages = min(3, total_pages)

            total_chars = 0
            for i in range(check_pages):
                text = reader.pages[i].extract_text() or ""
                total_chars += len(text.strip())

            avg_chars_per_page = total_chars / check_pages if check_pages > 0 else 0

            # 페이지당 50자 미만이면 OCR 필요
            needs_ocr = avg_chars_per_page < 50

            if needs_ocr:
                logger.info(f"   📷 이미지 PDF 감지: 평균 {avg_chars_per_page:.0f}자/페이지")
            else:
                logger.info(f"   📝 텍스트 PDF 감지: 평균 {avg_chars_per_page:.0f}자/페이지")

            return needs_ocr

        except Exception as e:
            logger.warning(f"   ⚠️  PDF 확인 오류: {e}")
            return False

    def run_ocr(self, file_path: Path) -> Optional[Path]:
        """
        OCR 실행 후 텍스트 파일 반환

        Args:
            file_path: PDF 파일 경로

        Returns:
            OCR 결과 텍스트 파일 경로 (실패 시 None)
        """
        try:
            from ocr_pdf_processor import ocr_pdf, check_pdf_has_text
        except ImportError:
            # ocr_pdf_processor가 없으면 직접 구현
            logger.warning("   ⚠️  ocr_pdf_processor 모듈을 찾을 수 없습니다.")
            return None

        output_path = file_path.with_suffix(".txt")

        logger.info(f"   🔍 OCR 처리 중... (언어: {self.ocr_languages})")

        try:
            text = ocr_pdf(
                str(file_path),
                output_path=str(output_path),
                languages=self.ocr_languages
            )

            if output_path.exists():
                logger.info(f"   ✅ OCR 완료: {output_path.name}")
                return output_path
            else:
                logger.error(f"   ❌ OCR 결과 파일이 생성되지 않았습니다.")
                return None

        except Exception as e:
            logger.error(f"   ❌ OCR 실패: {e}")
            return None

    def run_processor(self, file_path: Path, chunk_size: int = 2800, overlap: int = 560) -> bool:
        """
        PDF/TXT 처리 (local_pdf_processor.py 호출)

        Args:
            file_path: 처리할 파일 경로
            chunk_size: 청크 크기
            overlap: 오버랩 크기

        Returns:
            성공 여부
        """
        processor_script = self.script_dir / "local_pdf_processor.py"

        if not processor_script.exists():
            logger.error(f"   ❌ 프로세서 스크립트를 찾을 수 없습니다: {processor_script}")
            return False

        logger.info(f"   📄 청킹 처리 중 (Size: {chunk_size}, Overlap: {overlap})...")

        try:
            # v2.2: 실시간 로그 출력을 위해 Popen 사용 가능하지만, 
            # 여기서는 일단 일관성을 위해 매개변수 전달에 집중
            cmd = [
                self.python_exe,
                str(processor_script),
                str(file_path),
                "-o", str(self.inbox_dir),
                "--chunk-size", str(chunk_size),
                "--overlap", str(overlap)
            ]
            
            # 실시간 로그 출력을 위해 직접 실행 (Streamlit에서 캡처 가능하도록)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            for line in process.stdout:
                line = line.strip()
                if line:
                    # [PROGRESS] 태그가 있으면 그대로 출력하여 app.py에서 인식 가능하게 함
                    print(line, flush=True)
                    if "[PROGRESS]" not in line:
                        logger.debug(f"      {line}")

            process.wait()

            if process.returncode == 0:
                logger.info(f"   ✅ 청킹 완료")
                return True
            else:
                logger.error(f"   ❌ 청킹 실패 (Exit Code: {process.returncode})")
                return False

        except Exception as e:
            logger.error(f"   ❌ 청킹 오류: {e}")
            return False

    def run_db_builder(self) -> bool:
        """
        ChromaDB 인덱싱 실행 (db_builder.py 호출)

        Returns:
            성공 여부
        """
        db_builder_script = self.script_dir / "db_builder.py"

        if not db_builder_script.exists():
            logger.error(f"   ❌ DB 빌더 스크립트를 찾을 수 없습니다: {db_builder_script}")
            return False

        logger.info(f"   🗄️  벡터 DB 인덱싱 중...")

        try:
            result = subprocess.run(
                [self.python_exe, str(db_builder_script)],
                capture_output=True,
                text=True,
                timeout=600  # 10분 타임아웃
            )

            if result.returncode == 0:
                logger.info(f"   ✅ 인덱싱 완료")
                return True
            else:
                logger.error(f"   ❌ 인덱싱 실패: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"   ❌ 인덱싱 시간 초과")
            return False
        except Exception as e:
            logger.error(f"   ❌ 인덱싱 오류: {e}")
            return False

    def run_lemma_indexer(self) -> bool:
        """
        Lemma 인덱스 업데이트 (build_lemma_index.py 호출)

        Returns:
            성공 여부
        """
        indexer_script = self.tools_dir / "build_lemma_index.py"

        if not indexer_script.exists():
            logger.warning(f"   ⚠️  Lemma 인덱서를 찾을 수 없습니다: {indexer_script}")
            return True  # 선택적 단계

        logger.info(f"   📑 Lemma 인덱스 업데이트 중...")

        try:
            result = subprocess.run(
                [self.python_exe, str(indexer_script)],
                capture_output=True,
                text=True,
                timeout=120  # 2분 타임아웃
            )

            if result.returncode == 0:
                logger.info(f"   ✅ 인덱스 업데이트 완료")
                return True
            else:
                logger.warning(f"   ⚠️  인덱스 업데이트 경고: {result.stderr}")
                return True  # 경고만 표시

        except Exception as e:
            logger.warning(f"   ⚠️  인덱스 업데이트 오류: {e}")
            return True  # 선택적 단계

    def process_file(self, file_path: Path, chunk_size: int = 2800, overlap: int = 560) -> Dict[str, Any]:
        """
        단일 파일 처리 (전체 파이프라인)

        Args:
            file_path: 처리할 파일 경로
            chunk_size: 청크 크기
            overlap: 오버랩 크기

        Returns:
            처리 결과 딕셔너리
        """
        result = {
            "file": file_path.name,
            "status": "pending",
            "ocr_applied": False,
            "started_at": datetime.now().isoformat(),
            "errors": []
        }

        logger.info(f"\n📂 파일 처리 시작: {file_path.name}")

        # 1. OCR 필요 여부 확인 및 실행
        if self.ocr_enabled and file_path.suffix.lower() == ".pdf":
            if self.check_needs_ocr(file_path):
                ocr_result = self.run_ocr(file_path)
                if ocr_result:
                    result["ocr_applied"] = True
                    file_path = ocr_result  # OCR 결과로 대체
                else:
                    result["errors"].append("OCR 실패")
                    # OCR 실패해도 원본으로 계속 진행

        # 2. 청킹 처리
        if not self.run_processor(file_path, chunk_size=chunk_size, overlap=overlap):
            result["errors"].append("청킹 실패")
            result["status"] = "failed"
            return result

        result["status"] = "success"
        result["completed_at"] = datetime.now().isoformat()

        return result

    def cleanup_processed_file(self, file_path: Path) -> bool:
        """
        처리 완료된 파일 정리
        - JSON (청킹 결과) → archive/로 이동 (검색 데이터)
        - PDF/TXT/매핑 파일 → 삭제 (사용자 원본은 별도 보관)

        Args:
            file_path: 원본 파일 경로

        Returns:
            성공 여부
        """
        try:
            stem = file_path.stem
            
            # 1. JSON 파일을 archive로 이동 (검색용 데이터)
            json_file = file_path.with_suffix(".json")
            if json_file.exists():
                self.archive_dir.mkdir(parents=True, exist_ok=True)
                dest = self.archive_dir / json_file.name
                shutil.move(str(json_file), str(dest))
                logger.info(f"   📦 이동: {json_file.name} → archive/")
            
            # 2. 임시 파일들 삭제 (PDF, 매핑, OCR TXT)
            temp_files = [
                file_path,                              # 원본 PDF
                file_path.with_suffix(".mapping.json"), # 매핑 파일
                file_path.with_suffix(".txt"),          # OCR 결과
            ]
            
            for f in temp_files:
                if f.exists():
                    f.unlink()
                    logger.info(f"   🗑️  삭제: {f.name}")

            return True

        except Exception as e:
            logger.warning(f"   ⚠️  파일 정리 실패: {e}")
            return False

    def process_inbox(self, chunk_size: int = 2800, overlap: int = 560) -> Dict[str, Any]:
        """
        inbox 폴더 전체 처리

        Returns:
            처리 결과 요약
        """
        summary = {
            "started_at": datetime.now().isoformat(),
            "files_processed": 0,
            "files_failed": 0,
            "ocr_applied": 0,
            "results": []
        }

        logger.info("=" * 60)
        logger.info("🏭 Theology AI Lab - 통합 파이프라인 시작")
        logger.info("=" * 60)
        logger.info(f"📂 Inbox: {self.inbox_dir}")
        logger.info(f"📂 Archive: {self.archive_dir}")
        logger.info(f"🔍 OCR 활성화: {self.ocr_enabled}")
        logger.info(f"📏 인덱싱 설정: Chunk={chunk_size}, Overlap={overlap}")

        # 처리할 파일 목록
        files = list(self.inbox_dir.glob("*.pdf")) + list(self.inbox_dir.glob("*.txt")) + list(self.inbox_dir.glob("*.epub"))

        # JSON 파일은 제외 (이미 처리됨)
        files = [f for f in files if not f.name.endswith(".json")]

        if not files:
            logger.info("\n✅ 처리할 파일이 없습니다.")
            return summary

        logger.info(f"\n📄 발견된 파일: {len(files)}개")
        total_files = len(files)

        # 개별 파일 처리
        processed_files = []  # 성공한 파일 목록

        for i, file_path in enumerate(files, 1):
            # [v2.7.23] 개선된 진행률 표시
            progress_pct = int((i - 1) / total_files * 80)  # 파일 처리는 0-80%
            print(f"[PROGRESS] {progress_pct}% ({i}/{total_files}) 📄 {file_path.name} 처리 중...", flush=True)
            
            logger.info(f"\n[{i}/{len(files)}] {'─' * 50}")
            result = self.process_file(file_path, chunk_size=chunk_size, overlap=overlap)
            summary["results"].append(result)

            if result["status"] == "success":
                summary["files_processed"] += 1
                processed_files.append(file_path)
                progress_pct = int(i / total_files * 80)
                print(f"[PROGRESS] {progress_pct}% ({i}/{total_files}) ✅ {file_path.name} 완료", flush=True)
            else:
                summary["files_failed"] += 1
                print(f"[PROGRESS] {progress_pct}% ❌ {file_path.name} 실패", flush=True)

            if result.get("ocr_applied"):
                summary["ocr_applied"] += 1

        # DB 인덱싱 (전체 처리 후 한 번만)
        logger.info(f"\n{'─' * 60}")
        if summary["files_processed"] > 0:
            print(f"[PROGRESS] 85% 🗄️ 벡터 DB 인덱싱 시작...", flush=True)
            self.run_db_builder()
            print(f"[PROGRESS] 95% 📑 Lemma 인덱스 업데이트 중...", flush=True)
            self.run_lemma_indexer()

            # 성공한 파일들 inbox에서 정리
            logger.info(f"\n🧹 처리 완료된 파일 정리 중...")
            for file_path in processed_files:
                self.cleanup_processed_file(file_path)

        # 완료 요약
        summary["completed_at"] = datetime.now().isoformat()
        print(f"[PROGRESS] 100% (파이프라인 완료)")

        logger.info("\n" + "=" * 60)
        logger.info("🎉 파이프라인 완료!")
        logger.info("=" * 60)
        logger.info(f"   ✅ 성공: {summary['files_processed']}개")
        logger.info(f"   ❌ 실패: {summary['files_failed']}개")
        logger.info(f"   📷 OCR 적용: {summary['ocr_applied']}개")
        logger.info("=" * 60)

        return summary


def main():
    """CLI 엔트리포인트"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Theology AI Lab - 통합 처리 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # inbox 전체 처리
  python pipeline.py

  # 단일 파일 처리
  python pipeline.py /path/to/document.pdf

  # OCR 비활성화
  OCR_ENABLED=false python pipeline.py
        """
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="처리할 파일 경로 (생략 시 inbox 전체 처리)"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2800,
        help="청크 크기 (문자 수)"
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=560,
        help="청크 오버랩 (문자 수)"
    )

    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="OCR 처리 비활성화"
    )

    args = parser.parse_args()

    # OCR 비활성화 옵션 처리
    if args.no_ocr:
        os.environ["OCR_ENABLED"] = "false"

    # 파이프라인 실행
    pipeline = ProcessingPipeline()

    if args.input:
        # 단일 파일 처리
        file_path = Path(args.input)
        if not file_path.exists():
            logger.error(f"❌ 파일을 찾을 수 없습니다: {args.input}")
            sys.exit(1)

        result = pipeline.process_file(file_path, chunk_size=args.chunk_size, overlap=args.overlap)

        # DB 인덱싱
        if result["status"] == "success":
            print(f"[PROGRESS] 95% (벡터 DB 빌드 중...)")
            pipeline.run_db_builder()
            print(f"[PROGRESS] 98% (Lemma 인덱스 업데이트 중...)")
            pipeline.run_lemma_indexer()
            
            # v2.7.22: 단일 파일 처리 성공 후에도 정리 수행
            print(f"[PROGRESS] 99% (파일 정리 중...)")
            pipeline.cleanup_processed_file(file_path)
            
            print(f"[PROGRESS] 100% (완료)")

        sys.exit(0 if result["status"] == "success" else 1)
    else:
        # inbox 전체 처리
        summary = pipeline.process_inbox(chunk_size=args.chunk_size, overlap=args.overlap)
        sys.exit(0 if summary["files_failed"] == 0 else 1)


if __name__ == "__main__":
    main()
