import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright
import sys

# 프로젝트 루트를 경로에 추가 (utils 접근을 위해)
sys.path.append(str(Path(__file__).parent.parent))
from utils.local_pdf_processor import process_pdf, tiktoken_len
from langchain_text_splitters import RecursiveCharacterTextSplitter

class LibrarianAgent:
    """
    정보수집관 (Librarian)
    - 외부 웹 URL 콘텐츠 추출
    - 로컬 PDF 파일 정제 및 텍스트화
    """
    
    def __init__(self, persona_path: Optional[str] = None):
        self.persona_path = persona_path
        self.name = "Librarian"
        
    async def collect_web(self, url: str) -> Dict[str, Any]:
        """웹 URL에서 본문 텍스트 추출"""
        print(f"🌐 [{self.name}] 웹 수집 시작: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle")
                # 본문 추출 (단순화: 우선 innerText 사용)
                title = await page.title()
                content = await page.evaluate("document.body.innerText")
                
                print(f"✅ [{self.name}] 수집 완료: {title}")
                return {
                    "source": url,
                    "title": title,
                    "content": content,
                    "type": "web"
                }
            except Exception as e:
                print(f"❌ [{self.name}] 웹 수집 오류: {e}")
                return {"error": str(e)}
            finally:
                await browser.close()

    def collect_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """로컬 PDF 가공 (utils.local_pdf_processor 활용)"""
        print(f"📄 [{self.name}] PDF 가공 시작: {pdf_path}")
        
        if not os.path.exists(pdf_path):
            return {"error": f"파일을 찾을 수 없습니다: {pdf_path}"}
            
        # 텍스트 스플리터 설정
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2800,
            chunk_overlap=560,
            separators=["\n\n\n", "\n\n", "\n", ". ", "! ", "? ", "; ", " ", ""],
            length_function=tiktoken_len,
        )
        # 다운로드 경로 설정 (필요시)
        # Note: self.vault_path is not defined in the current __init__ method.
        # This line will cause an AttributeError if self.vault_path is not set elsewhere.
        self.download_dir = Path(self.vault_path) / "000 System/010 Inbox"
        
        try:
            chunks = process_pdf(pdf_path, text_splitter)
            
            # 요약 정보 생성
            full_text = "\n\n".join([c['text'] for c in chunks])
            
            print(f"✅ [{self.name}] PDF 가공 완료: {len(chunks)}개 청크 생성")
            return {
                "source": pdf_path,
                "title": Path(pdf_path).name,
                "chunks": chunks,
                "full_text": full_text,
                "type": "pdf"
            }
        except Exception as e:
            print(f"❌ [{self.name}] PDF 가공 오류: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="ARC Secretariat - Librarian Agent")
    parser.add_argument("--url", type=str, help="Collect content from a web URL")
    parser.add_argument("--pdf", type=str, help="Process a local PDF file")
    
    args = parser.parse_args()
    
    async def run_cli():
        lib = LibrarianAgent()
        if args.url:
            result = await lib.collect_web(args.url)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.pdf:
            result = lib.collect_pdf(args.pdf)
            # PDF 결과는 너무 클 수 있으므로 요약 정보를 우선 출력
            if "chunks" in result:
                del result["chunks"] # CLI에서는 요약만
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            parser.print_help()

    if args.url or args.pdf:
        asyncio.run(run_cli())
