#!/usr/bin/env python3
"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  steward.py — Tech Steward (기술 청지기) Agent                        ┃
┃                                                                       ┃
┃  "연구자는 사유에만 집중하십시오.                                      ┃
┃   기술 인프라 관리는 제가 맡겠습니다."                                 ┃
┃                                                                       ┃
┃  Usage:                                                               ┃
┃    python steward.py --scan              # 프로젝트 스캔              ┃
┃    python steward.py --audit-venv        # venv 상태 점검             ┃
┃    python steward.py --check-pipeline    # 파이프라인 상태 확인       ┃
┃    python steward.py --clean             # 불필요 파일 정리 제안      ┃
┃                                                                       ┃
┃  Author: ARC Secretariat                                              ┃
┃  Version: 1.0.0                                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════
# 📌 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

def discover_paths() -> Dict[str, Path]:
    """프로젝트 경로 자동 탐지"""
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent  # theology-vector-db
    
    # Projects.nosync 폴더 찾기
    projects_path = project_root.parent  # Projects.nosync
    
    return {
        "project_root": project_root,
        "projects_dir": projects_path,
        "agents_dir": script_dir,
        "venv": project_root / "venv.nosync",
    }

PATHS = discover_paths()


class TechSteward:
    """
    기술 청지기 (Tech Steward)
    - 파이프라인 상태 모니터링
    - 환경 청소 및 정리
    - 프로젝트 기록 관리
    """
    
    def __init__(self):
        self.name = "Tech Steward"
        self.paths = PATHS
        
    # ═══════════════════════════════════════════════════════════════════
    # 🔍 PROJECT SCANNER
    # ═══════════════════════════════════════════════════════════════════
    
    def scan_projects(self) -> List[Dict[str, Any]]:
        """Projects.nosync 폴더 내 모든 프로젝트 스캔"""
        print(f"🔍 [{self.name}] 프로젝트 스캔 중...")
        
        projects_dir = self.paths["projects_dir"]
        if not projects_dir.exists():
            return [{"error": f"경로를 찾을 수 없습니다: {projects_dir}"}]
        
        projects = []
        for item in sorted(projects_dir.iterdir()):
            if item.is_dir() and not item.name.startswith('.'):
                project_info = self._analyze_project(item)
                projects.append(project_info)
        
        print(f"✅ [{self.name}] {len(projects)}개 프로젝트 발견")
        return projects
    
    def _analyze_project(self, path: Path) -> Dict[str, Any]:
        """단일 프로젝트 분석"""
        info = {
            "name": path.name,
            "path": str(path),
            "has_readme": (path / "README.md").exists(),
            "has_venv": False,
            "venv_size_mb": 0,
            "has_requirements": (path / "requirements.txt").exists(),
            "has_git": (path / ".git").exists(),
            "file_count": 0,
            "last_modified": None,
        }
        
        # venv 탐지
        for venv_name in ["venv", "venv.nosync", ".venv", ".venv.nosync"]:
            venv_path = path / venv_name
            if venv_path.exists():
                info["has_venv"] = True
                info["venv_size_mb"] = self._get_dir_size_mb(venv_path)
                break
        
        # 파일 수 계산 (얕은 탐색)
        try:
            info["file_count"] = len(list(path.glob("*")))
            # 가장 최근 수정 시간
            latest = max(path.glob("*"), key=lambda x: x.stat().st_mtime, default=None)
            if latest:
                info["last_modified"] = datetime.fromtimestamp(latest.stat().st_mtime).isoformat()
        except Exception:
            pass
        
        return info
    
    def _get_dir_size_mb(self, path: Path) -> float:
        """디렉토리 용량 계산 (MB)"""
        try:
            result = subprocess.run(
                ["du", "-sm", str(path)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return float(result.stdout.split()[0])
        except Exception:
            pass
        return 0
    
    # ═══════════════════════════════════════════════════════════════════
    # 🧹 VENV AUDITOR
    # ═══════════════════════════════════════════════════════════════════
    
    def audit_venv(self) -> Dict[str, Any]:
        """모든 venv 상태 점검"""
        print(f"🧹 [{self.name}] venv 상태 점검 중...")
        
        projects = self.scan_projects()
        venvs = []
        total_size = 0
        
        for proj in projects:
            if proj.get("has_venv"):
                venvs.append({
                    "project": proj["name"],
                    "size_mb": proj["venv_size_mb"],
                })
                total_size += proj["venv_size_mb"]
        
        # 크기순 정렬
        venvs.sort(key=lambda x: x["size_mb"], reverse=True)
        
        report = {
            "total_venvs": len(venvs),
            "total_size_gb": round(total_size / 1024, 2),
            "venvs": venvs,
            "recommendation": self._generate_venv_recommendation(venvs, total_size)
        }
        
        print(f"✅ [{self.name}] {len(venvs)}개 venv 발견, 총 {report['total_size_gb']}GB")
        return report
    
    def _generate_venv_recommendation(self, venvs: List[Dict], total_size: float) -> str:
        """venv 정리 권장 사항 생성"""
        if total_size > 5000:  # 5GB 초과
            large_venvs = [v for v in venvs if v["size_mb"] > 500]
            return f"⚠️ 총 용량이 {total_size/1024:.1f}GB로 큽니다. {len(large_venvs)}개의 대형 venv 통합을 권장합니다."
        elif total_size > 2000:  # 2GB 초과
            return "💡 venv 용량이 다소 큽니다. 미사용 프로젝트 정리를 고려하세요."
        else:
            return "✅ venv 상태가 양호합니다."
    
    # ═══════════════════════════════════════════════════════════════════
    # 🔧 PIPELINE GUARDIAN
    # ═══════════════════════════════════════════════════════════════════
    
    def check_pipeline(self) -> Dict[str, Any]:
        """파이프라인 상태 확인"""
        print(f"🔧 [{self.name}] 파이프라인 상태 확인 중...")
        
        checks = {
            "run_pipeline_sh": self._check_file_exists("run_pipeline.sh"),
            "venv_python": self._check_python_version(),
            "chromadb": self._check_chromadb(),
            "inbox_writable": self._check_inbox(),
        }
        
        all_ok = all(c.get("status") == "ok" for c in checks.values())
        
        return {
            "overall_status": "✅ 정상" if all_ok else "⚠️ 점검 필요",
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }
    
    def _check_file_exists(self, filename: str) -> Dict[str, str]:
        """파일 존재 여부 확인"""
        path = self.paths["project_root"] / filename
        if path.exists():
            return {"status": "ok", "message": f"{filename} 존재함"}
        return {"status": "error", "message": f"{filename} 없음"}
    
    def _check_python_version(self) -> Dict[str, str]:
        """Python 버전 확인"""
        venv_python = self.paths["venv"] / "bin" / "python3"
        if not venv_python.exists():
            return {"status": "error", "message": "venv Python을 찾을 수 없음"}
        
        try:
            result = subprocess.run(
                [str(venv_python), "--version"],
                capture_output=True, text=True, timeout=10
            )
            version = result.stdout.strip()
            if "3.11" in version or "3.10" in version:
                return {"status": "ok", "message": version}
            return {"status": "warning", "message": f"{version} (3.11 권장)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _check_chromadb(self) -> Dict[str, str]:
        """ChromaDB 상태 확인"""
        # Theology_Project.nosync/vector_db 확인
        vector_db = self.paths["projects_dir"] / "Theology_Project.nosync" / "vector_db"
        if vector_db.exists():
            size = self._get_dir_size_mb(vector_db)
            return {"status": "ok", "message": f"ChromaDB 존재 ({size:.0f}MB)"}
        return {"status": "warning", "message": "vector_db 폴더 없음"}
    
    def _check_inbox(self) -> Dict[str, str]:
        """Inbox 폴더 쓰기 권한 확인"""
        inbox = self.paths["projects_dir"] / "Theology_Project.nosync" / "inbox"
        if inbox.exists() and os.access(inbox, os.W_OK):
            return {"status": "ok", "message": "inbox 쓰기 가능"}
        return {"status": "error", "message": "inbox 접근 불가"}
    
    # ═══════════════════════════════════════════════════════════════════
    # 🗑️ CLEANUP SUGGESTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    def suggest_cleanup(self) -> Dict[str, Any]:
        """정리 대상 파일/폴더 제안"""
        print(f"🗑️ [{self.name}] 정리 대상 탐색 중...")
        
        suggestions = {
            "temp_files": [],
            "duplicate_venvs": [],
            "no_readme_projects": [],
            "empty_projects": [],
        }
        
        projects = self.scan_projects()
        
        for proj in projects:
            # README 없는 프로젝트
            if not proj.get("has_readme"):
                suggestions["no_readme_projects"].append(proj["name"])
            
            # 파일이 거의 없는 프로젝트
            if proj.get("file_count", 0) <= 2:
                suggestions["empty_projects"].append(proj["name"])
        
        # 임시 파일 탐색
        for pattern in ["*.log", "*.tmp", "__pycache__", ".DS_Store"]:
            for f in self.paths["project_root"].rglob(pattern):
                if "__pycache__" not in str(f.parent):
                    suggestions["temp_files"].append(str(f.relative_to(self.paths["project_root"])))
        
        return suggestions


# ═══════════════════════════════════════════════════════════════════════════
# 🚀 CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Tech Steward - 기술 인프라 관리 에이전트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scan              프로젝트 목록 스캔
  %(prog)s --audit-venv        venv 용량 점검
  %(prog)s --check-pipeline    파이프라인 상태 확인
  %(prog)s --clean             정리 대상 제안
        """
    )
    
    parser.add_argument("--scan", action="store_true", help="프로젝트 스캔")
    parser.add_argument("--audit-venv", action="store_true", help="venv 상태 점검")
    parser.add_argument("--check-pipeline", action="store_true", help="파이프라인 상태 확인")
    parser.add_argument("--clean", action="store_true", help="정리 대상 제안")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")
    
    args = parser.parse_args()
    
    steward = TechSteward()
    result = None
    
    if args.scan:
        result = steward.scan_projects()
    elif args.audit_venv:
        result = steward.audit_venv()
    elif args.check_pipeline:
        result = steward.check_pipeline()
    elif args.clean:
        result = steward.suggest_cleanup()
    else:
        parser.print_help()
        return
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
