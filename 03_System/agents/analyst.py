from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import os

class AnalystAgent:
    """
    분석관 (Analyst)
    - 지혜의 환원 (200 -> 100) 제안
    - 교차 연결 (Cross-linking) 발견
    """
    
    def __init__(self, vault_path: Optional[str] = None):
        self.name = "Analyst"
        self.vault_path = vault_path or "/Users/msn/Desktop/MS_Brain.nosync"

    def scan_ministry(self, limit: int = 5) -> List[Dict[str, Any]]:
        """최근 목회/묵상 노트를 스캔하여 분석 후보 목록 반환"""
        print(f"🧐 [{self.name}] 200 Ministry 폴더 스캔 중...")
        ministry_path = Path(self.vault_path) / "200 Ministry"
        if not ministry_path.exists():
            return []
            
        notes = []
        # .md 파일들을 수정 시간 순으로 정렬하여 탐색
        for file in sorted(ministry_path.glob("**/*.md"), key=os.path.getmtime, reverse=True):
            if len(notes) >= limit:
                break
            
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # 제목(H1) 추출 시도
                    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                    title = title_match.group(1) if title_match else file.stem
                    
                    notes.append({
                        "filename": file.name,
                        "path": str(file.relative_to(self.vault_path)),
                        "title": title,
                        "excerpt": content[:500] + "..."
                    })
            except Exception as e:
                print(f"⚠️ [{self.name}] 파일 읽기 오류 ({file.name}): {e}")
                
        return notes

    def analyze_ministry_note(self, note_content: str) -> Dict[str, Any]:
        """목회/묵상 노트를 분석하여 신학 개념 추출 제안 (AI 비서실장용 데이터 제공)"""
        # Antigravity가 직접 분석할 수 있도록 노트를 정제하여 반환하는 역할로 집중
        return {
            "note_summary": note_content[:1000],
            "structural_elements": re.findall(r"^##\s+(.+)$", note_content, re.MULTILINE)
        }

    def suggest_links(self, query: str, context_results: List[Dict[str, Any]]) -> List[str]:
        """검색 결과를 바탕으로 연관된 노트 연결 제안"""
        links = []
        for res in context_results:
            meta = res.get("metadata", {})
            if "filename" in meta:
                links.append(f"[[{meta['filename']}]]")
if __name__ == "__main__":
    import argparse
    import json
    import sys
    import os

    parser = argparse.ArgumentParser(description="ARC Secretariat - Analyst Agent")
    parser.add_argument("--note", type=str, help="Content of the note to analyze")
    parser.add_argument("--file", type=str, help="Path to a file to analyze")
    parser.add_argument("--query", type=str, help="Query for suggesting links")
    parser.add_argument("--scan", action="store_true", help="Scan for recent ministry notes")
    parser.add_argument("--limit", type=int, default=5, help="Limit for scanning")
    
    args = parser.parse_args()
    
    analyst = AnalystAgent()
    
    if args.scan:
        result = analyst.scan_ministry(limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.note or args.file:
        content = args.note
        if args.file:
            if os.path.exists(args.file):
                with open(args.file, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                print(json.dumps({"error": "File not found"}, ensure_ascii=False))
                sys.exit(1)
        result = analyst.analyze_ministry_note(content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.query:
        # 시뮬레이션을 위해 빈 리스트 전달
        result = analyst.suggest_links(args.query, [])
        print(json.dumps({"suggested_links": result}, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
