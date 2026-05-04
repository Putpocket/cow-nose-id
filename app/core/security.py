# 비밀번호 해시 라이브러리
from passlib.context import CryptContext

# bcrypt 방식 사용
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 비밀번호 해시 함수
def hash_password(password: str):
    return pwd_context.hash(password)

# 비밀번호 검증 함수
def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)