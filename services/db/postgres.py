# ==============================
# 환경변수 및 DB 라이브러리 import
# ==============================

import os  # 환경변수 사용을 위한 라이브러리
import psycopg2  # PostgreSQL 연결 라이브러리


# ==============================
# DB 연결 설정
# ==============================

# 환경변수에서 DB 접속 정보 가져오기
# (.env 파일에 저장된 값을 불러옴)
DB_HOST = os.getenv("DB_HOST")        # DB 서버 주소
DB_NAME = os.getenv("DB_NAME")        # 사용할 DB 이름
DB_USER = os.getenv("DB_USER")        # DB 사용자명
DB_PASSWORD = os.getenv("DB_PASSWORD")# DB 비밀번호
DB_PORT = os.getenv("DB_PORT")        # 포트 번호


# ==============================
# DB 연결 함수
# ==============================

def get_connection():
    """
    PostgreSQL DB 연결을 생성하는 함수
    요청마다 새로운 연결을 생성하는 방식 (안전한 방식)
    """
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )


# ==============================
# 소 정보 조회 함수
# ==============================

def get_cow_info(cow_id):
    """
    cow_id를 기반으로 DB에서 소 정보를 조회하는 함수

    Args:
        cow_id (int): 조회할 소의 ID

    Returns:
        dict: 소 정보 또는 에러 메시지
    """

    # DB 연결 생성
    conn = get_connection()

    # 커서 생성 (DB 작업을 수행하는 객체)
    cursor = conn.cursor()

    try:
        # SQL 실행 (%s 사용 → SQL 인젝션 방지)
        cursor.execute(
            "SELECT cow_id, name FROM cows WHERE cow_id=%s",
            (cow_id,)
        )

        # 결과 한 개 가져오기
        data = cursor.fetchone()

        # 데이터가 없는 경우
        if data is None:
            return {"error": "cow not found"}

        # 결과를 JSON 형태로 반환
        return {
            "cow_id": data[0],
            "name": data[1]
        }

    except Exception as e:
        # DB 오류 발생 시 에러 메시지 반환
        return {"error": str(e)}

    finally:
        # 커서와 연결을 반드시 닫아야 함 (자원 누수 방지)
        cursor.close()
        conn.close()