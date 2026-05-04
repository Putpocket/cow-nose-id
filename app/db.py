# app/db.py
import psycopg2
from app.config import settings

def get_connection():
    """
    PostgreSQL DB 연결 생성 (설정값 기반)
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

def get_cow_info(cow_id):
    """
    cow_id를 기반으로 소 및 소유주 정보 조회
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 조장님 피드백 반영: 소유주 정보까지 JOIN으로 가져오기
        query = """
            SELECT c.cow_id, c.name, c.ear_tag, c.breed, o.name as owner_name
            FROM cows c
            LEFT JOIN owners o ON c.owner_id = o.owner_id
            WHERE c.cow_id = %s
        """
        cursor.execute(query, (cow_id,))
        data = cursor.fetchone()

        if data is None:
            return None

        return {
            "cow_id": data[0],
            "name": data[1],
            "ear_tag": data[2],
            "breed": data[3],
            "owner_name": data[4]
        }
    except Exception:
        return {"error": "database error"}
    finally:
        cursor.close()
        conn.close()

def add_audit_log(action, user_id=None, username=None, target_type=None, 
                  target_id=None, ip_address=None, user_agent=None, detail=None):
    """
    주요 작업에 대한 감사 로그 기록 (조장님 피드백 10번 반영)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
            INSERT INTO audit_logs (
                user_id, username, action, target_type, target_id, 
                ip_address, user_agent, detail
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            user_id, username, action, target_type, 
            target_id, ip_address, user_agent, detail
        ))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()