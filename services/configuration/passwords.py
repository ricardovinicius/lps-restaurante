import hashlib
import secrets


def derive(password: str, salt: str) -> str:
    return hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=2**15, r=8, p=1, maxmem=64 * 1024**2,
    ).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}:{derive(password, salt)}"


def verify_password(password: str, stored: str) -> bool:
    salt, expected = stored.split(":", 1)
    return secrets.compare_digest(derive(password, salt), expected)
