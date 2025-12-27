from pathlib import Path
from typing import List, Dict, Any, Optional

class GardenerAgent:
    """
    관리관 (Gardener)
    - 볼트 무결성 및 RAG 위생 관리
    - 메타데이터 검증
    """
    
    def __init__(self, vault_path: Optional[str] = None):
        self.name = "Gardener"
        self.vault_path = vault_path or "/Users/msn/Desktop/MS_Brain.nosync"

    def check_vault_hygiene(self) -> Dict[str, Any]:
        """볼트 전체를 스캔하여 위생 상태 점검"""
        print(f"🎋 [{self.name}] 볼트 위생 점검 중...")
        report = {
            "broken_links": [],
            "missing_metadata": [],
            "total_notes": 0
        }
        
        for file in Path(self.vault_path).glob("**/*.md"):
            if ".nosync" in str(file) or ".obsidian" in str(file):
                continue
                
            report["total_notes"] += 1
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    # 1. 메타데이터 (YAML) 유무 확인
                    if not content.startswith("---"):
                        report["missing_metadata"].append(str(file.relative_to(self.vault_path)))
                    
                    # 2. 깨진 링크 탐지 (단순화된 정규식)
                    links = re.findall(r"\[\[(.+?)\]\]", content)
                    for link in links:
                        # 별칭(Alias) 처리
                        link_target = link.split("|")[0]
                        # 실제 파일 존재 여부 확인 (경로 탐색 제외 단순화)
                        if not self._check_link_exists(link_target):
                            report["broken_links"].append({
                                "file": str(file.relative_to(self.vault_path)),
                                "target": link_target
                            })
                            
            except Exception as e:
                print(f"⚠️ [{self.name}] 파일 스캔 오류 ({file.name}): {e}")
                
        return report

    def _check_link_exists(self, target: str) -> bool:
        """링크 타겟이 볼트 내에 존재하는지 확인"""
        # (현 버전에서는 루트에서 단순 매칭 시도)
        for ext in [".md", ".pdf", ""]:
            if any(Path(self.vault_path).glob(f"**/{target}{ext}")):
                return True
        return False

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="ARC Secretariat - Gardener Agent")
    parser.add_argument("--check", action="store_true", help="Perform vault hygiene check")
    
    args = parser.parse_args()
    
    gardener = GardenerAgent()
    
    if args.check:
        result = gardener.check_vault_hygiene()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
