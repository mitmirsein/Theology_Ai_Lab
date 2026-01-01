#!/usr/bin/env python3
"""
신학 벡터 DB 빌더 (M1 맥북용)
- inbox/ 폴더의 JSON 파일을 ChromaDB로 벡터화
- 처리 완료 시 JSON은 archive/로 이동 (검색용)
- 중복 실행 방지: 락 파일 사용
"""

import os
import sys
import json
import shutil
import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

from dotenv import load_dotenv

# Load .env explicitly from the kit root (parent of 03_System)
current_dir = os.path.dirname(os.path.abspath(__file__))
# utils -> 03_System -> Theology_AI_Lab (Root)
kit_root = os.path.dirname(os.path.dirname(current_dir)) 
load_dotenv(os.path.join(kit_root, ".env"))

# =========================================================
# ⚙️ 설정 - 경로 탐지 (Env -> Relative -> Default)
# 우선순위: Env > Relative (Standard)
def get_path(env_var, default_rel):
    env_val = os.environ.get(env_var)
    if env_val:
        if env_val.startswith("."):
            return os.path.abspath(os.path.join(kit_root, env_val))
        return env_val
    return os.path.join(kit_root, default_rel)

INBOX_DIR = get_path("INBOX_DIR", "01_Library/inbox")
ARCHIVE_DIR = get_path("ARCHIVE_DIR", "01_Library/archive")
DB_PATH = get_path("CHROMA_DB_DIR", "02_Brain/vector_db")
LOCK_FILE = os.path.join(kit_root, ".db_builder.lock")
# =========================================================

def acquire_lock():
    """락 파일을 획득합니다. 이미 실행 중이면 종료."""
    if os.path.exists(LOCK_FILE):
        # 락 파일이 1시간 이상 오래되었으면 삭제 (좀비 락 방지)
        if os.path.getmtime(LOCK_FILE) < (datetime.now().timestamp() - 3600):
            os.remove(LOCK_FILE)
            print("⚠️ 오래된 락 파일 삭제됨")
        else:
            print("🔒 다른 db_builder 프로세스가 실행 중입니다. 종료합니다.")
            sys.exit(0)
    
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

def release_lock():
    """락 파일을 해제합니다."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def is_already_archived(filename):
    """파일이 이미 archive에 있는지 확인합니다."""
    return os.path.exists(os.path.join(ARCHIVE_DIR, filename))

def build_database():
    # 1. 폴더 확인 및 생성
    for path in [INBOX_DIR, ARCHIVE_DIR]:
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"📁 폴더 생성됨: {path}")

    # 2. 임베딩 모델 로드 (다국어 지원, 신학 분야 중요)
    print("🧠 모델 로딩 중... (paraphrase-multilingual-MiniLM-L12-v2)")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    # 3. DB 연결 (없으면 자동 생성)
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_or_create_collection(name="theology_library")
    print(f"📚 현재 DB 문서 수: {collection.count()}개")

    # 4. Inbox 스캔
    json_files = [f for f in os.listdir(INBOX_DIR) if f.endswith('.json')]
    
    if not json_files:
        print("📭 Inbox가 비어있습니다. JSON 파일을 넣어주세요.")
        return

    print(f"🚀 {len(json_files)}개의 새 파일을 발견했습니다!")

    # 5. 파일 처리 루프
    for filename in json_files:
        # 이미 archive에 있으면 스킵 (중복 방지)
        if is_already_archived(filename):
            print(f"⏭️ '{filename}' 이미 archive에 존재. 스킵.")
            # inbox에서 삭제
            os.remove(os.path.join(INBOX_DIR, filename))
            continue
            
        file_path = os.path.join(INBOX_DIR, filename)
        source_name = os.path.splitext(filename)[0]
        
        print(f"\n📄 Processing: {filename} ...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_char = f.read(1)
                f.seek(0)
                
                documents = []
                ids = []
                metadatas = []
                
                # JSON 또는 JSONL 자동 감지
                if first_char == '[':
                    data = json.load(f)
                else:
                    try:
                        # Try reading as single JSON object first
                        f.seek(0)
                        raw_data = json.load(f)
                        if isinstance(raw_data, dict) and 'chunks' in raw_data:
                            data = raw_data['chunks']
                            print(f"   💡 신규 포맷 감지 ({len(data)} 청크)")
                        elif isinstance(raw_data, dict):
                            data = [raw_data]
                        else:
                            # Not a dict or list (e.g. primitive), treat as single item? 
                            # But usually db builder expects dicts. 
                            data = [raw_data]
                    except json.JSONDecodeError:
                        # Failed to load as single JSON, try JSONL
                        f.seek(0)
                        data = [json.loads(line) for line in f if line.strip()]

                for item in data:
                    # 고유 ID 생성
                    unique_id = f"{source_name}_{item.get('id', hash(item.get('text', '')))}"
                    
                    # 메타데이터 정리
                    meta = item.get('metadata', {})
                    meta['source'] = source_name
                    meta['indexed_at'] = datetime.now().isoformat()
                    
                    # None 값 및 리스트 처리 (ChromaDB 호환성)
                    for k, v in list(meta.items()):
                        if v is None:
                            meta[k] = ""
                        elif isinstance(v, list):
                            # [v2.0] 리스트를 쉼표 구분 문자열로 변환
                            meta[k] = ", ".join(str(item) for item in v)
                    
                    documents.append(item['text'])
                    ids.append(unique_id)
                    metadatas.append(meta)

            # 배치 처리 (10개씩 - 사용자 피드백 반영)
            batch_size = 10
            total_chunks = len(documents)
            print(f"   📊 총 {total_chunks} 청크 벡터화 시작...", flush=True)

            for i in range(0, total_chunks, batch_size):
                batch_docs = documents[i : i + batch_size]
                batch_ids = ids[i : i + batch_size]
                batch_meta = metadatas[i : i + batch_size]
                
                # 벡터 변환
                embeddings = model.encode(batch_docs).tolist()
                
                # DB에 upsert
                collection.upsert(
                    ids=batch_ids,
                    documents=batch_docs,
                    embeddings=embeddings,
                    metadatas=batch_meta
                )
                
                # [v2.7.23] 진행률 표시 (매 배치마다)
                processed = min(i + batch_size, total_chunks)
                pct = int(processed / total_chunks * 100)
                print(f"   🔄 벡터화: {processed}/{total_chunks} ({pct}%)", flush=True)

            # 완료된 파일 archive로 이동
            shutil.move(file_path, os.path.join(ARCHIVE_DIR, filename))
            print(f"🎉 '{filename}' → archive 이동 완료")

        except Exception as e:
            print(f"❌ 오류 ({filename}): {e}")

    print(f"\n🏁 완료! 최종 DB 문서 수: {collection.count()}개")

if __name__ == "__main__":
    try:
        acquire_lock()
        build_database()
    finally:
        release_lock()
