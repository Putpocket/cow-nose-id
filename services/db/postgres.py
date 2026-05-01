# PostgreSQL 연결 라이브러리 import
import psycopg2

# DB 연결 (환경에 맞게 수정 필요)
conn = psycopg2.connect(
    host="localhost",       # DB 서버 주소
    database="cow_db",      # 사용할 DB 이름
    user="postgres",        # DB 사용자명
    password="비밀번호",     # DB 비밀번호
    port="5432"             # 포트 번호
)

# DB 작업을 위한 커서 생성
cursor = conn.cursor()


# cow_id로 소 정보를 조회하는 함수
def get_cow_info(cow_id):
    # SQL 실행 (%s 사용 → SQL 인젝션 방지)
    cursor.execute(
        "SELECT cow_id, name FROM cows WHERE cow_id=%s",
        (cow_id,)
    )

    # 결과 한 개 가져오기
    data = cursor.fetchone()

    # JSON 형태로 변환해서 반환
    return {
        "cow_id": data[0],
        "name": data[1]
    }