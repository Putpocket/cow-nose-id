from app.security import hash_password as _hash_password
from app.security import verify_password as _verify_password


def hash_password(password: str):
    return _hash_password(password)


def verify_password(plain, hashed):
    return _verify_password(hashed, plain)
