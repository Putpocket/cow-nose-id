import os
import json
import torch
import numpy as np
import faiss
from dotenv import load_dotenv
from app.db import get_db_connection  # DB 연결 함수 (미리 구현 필요)
from app.services.embedder import DinoEmbedder  # 특징 추출기

def build_index():
    # 1. 환경 변수 및 설정 로드
    load_dotenv()
    FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./data/cow_nose.faiss")
    FAISS_IDS_PATH = os.getenv("FAISS_IDS_PATH", "./data/cow_ids.json")
    
    # 2. 데이터베이스에서 이미지 목록 가져오기
    # 조장님 피드백: PostgreSQL 기준으로 처리
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT cow_id, image_path FROM cow_images")
    rows = cur.fetchall()
    
    if not rows:
        print("인덱싱할 데이터가 DB에 없습니다.")
        return

    # 3. 임베딩 모델 로드 (DINOv2)
    embedder = DinoEmbedder()
    
    embeddings = []
    cow_ids = []

    print(f"총 {len(rows)}개의 이미지 인덱싱 시작...")

    for cow_id, image_path in rows:
        if os.path.exists(image_path):
            try:
                # 특징 추출 (여기서 실제 AI 로직이 돕니다)
                vector = embedder.extract(image_path)
                embeddings.append(vector)
                cow_ids.append(cow_id)
            except Exception as e:
                print(f"에러 발생 ({image_path}): {e}")
        else:
            print(f"파일을 찾을 수 없음: {image_path}")

    # 4. FAISS 인덱스 생성 및 저장
    if embeddings:
        embeddings_np = np.vstack(embeddings).astype('float32')
        dimension = embeddings_np.shape[1]
        
        # L2 거리 기반 인덱스 생성
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_np)
        
        # 파일 저장 (보안 요건 반영: data/ 폴더 하위)
        os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
        faiss.write_index(index, FAISS_INDEX_PATH)
        
        # 인덱스 순서와 cow_id 매핑 저장
        with open(FAISS_IDS_PATH, 'w') as f:
            json.dump(cow_ids, f)
            
        print(f"성공: 인덱스가 {FAISS_INDEX_PATH}에 저장되었습니다.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    build_index()