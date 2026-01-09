from passlib.context import CryptContext

try:
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    hash = pwd_context.hash("password")
    print(f"Hash success: {hash}")
except Exception as e:
    print(f"Hash failed: {e}")
