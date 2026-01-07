#!/usr/bin/env python3
"""
theology-vector-db 관리 도구
- 특정 소스(Source) 데이터 삭제 기능
- DB 무결성 점검 및 통계
"""

import os
import chromadb
import argparse

# =========================================================
# ⚙️ 설정 - 외장하드 경로
BASE_PATH = os.path.expanduser("~/Desktop/MS_Dev.nosync/data/Theology_Project.nosync")
DB_PATH = os.path.join(BASE_PATH, "vector_db")
# =========================================================

def delete_source(source_name, force=False):
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(name="theology_library")
    
    print(f"🔍 소스 '{source_name}' 검색 중...")
    
    # 해당 소스의 문서 찾기
    results = collection.get(
        where={"source": source_name}
    )
    
    count = len(results['ids'])
    
    if count == 0:
        print(f"❌ 소스 '{source_name}'를 찾을 수 없거나 이미 삭제되었습니다.")
        return

    print(f"⚠️  소스 '{source_name}'로부터 생성된 {count}개의 청크를 삭제합니다.")
    
    if not force:
        confirm = input("정말로 삭제하시겠습니까? (y/n): ")
        if confirm.lower() != 'y':
            print("🛑 삭제가 취소되었습니다.")
            return

    collection.delete(
        where={"source": source_name}
    )
    
    print(f"✅ 삭제 완료! (총 {count}개 삭제됨)")
    print(f"📚 남은 DB 문서 수: {collection.count()}개")

def show_stats():
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(name="theology_library")
    
    total = collection.count()
    print(f"\n📊 DB 통계 (경로: {DB_PATH})")
    print(f"------------------------------------")
    print(f"전체 문서(청크) 수: {total:,}개")
    
    # 소스별 통계는 대량 데이터에서 느릴 수 있으므로 샘플링하거나 ID 접두어로 추정 (여기선 간단히)
    # ChromaDB get()은 필터링을 지원하므로 소스가 뭔지 알면 카운트 가능
    # 실제 운영시에는 별도의 메타데이터 인덱스가 필요할 수 있음
    print(f"------------------------------------\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Theology Vector DB 매니저')
    parser.add_argument('--delete-source', type=str, help='삭제할 소스명 (파일명과 동일)')
    parser.add_argument('--yes', action='store_true', help='확인 절차 생략 (강제 삭제)')
    parser.add_argument('--stats', action='store_true', help='DB 통계 표시')
    
    args = parser.parse_args()
    
    if args.delete_source:
        delete_source(args.delete_source, force=args.yes)
    elif args.stats:
        show_stats()
    else:
        parser.print_help()
