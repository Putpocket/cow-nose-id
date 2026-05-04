import psycopg2  # PostgreSQL 연결 라이브러리
from app.config import settings


# ==============================
# DB 연결 함수
# ==============================

def get_connection():
    """
    PostgreSQL DB 연결을 생성하는 함수
    요청마다 새로운 연결을 생성하는 방식 (안전한 방식)
    """
    if settings.database_url:
        return psycopg2.connect(settings.database_url)
    return psycopg2.connect(
        host=settings.db_host,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        port=settings.db_port
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

    except Exception:
        return {"error": "database error"}

    finally:
        # 커서와 연결을 반드시 닫아야 함 (자원 누수 방지)
        cursor.close()
        conn.close()


def add_audit_log(
    action,
    user_id=None,
    username=None,
    target_type=None,
    target_id=None,
    ip_address=None,
    user_agent=None,
    detail=None,
):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO audit_logs (
                user_id,
                username,
                action,
                target_type,
                target_id,
                ip_address,
                user_agent,
                detail
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, username, action, target_type, target_id, ip_address, user_agent, detail),
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
