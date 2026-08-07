"""
Minimal password hashing helper.
NOTE: sha256 is used here only to keep the demo dependency-free.
For production, swap this for passlib[bcrypt] or argon2-cffi —
call sites elsewhere in the app don't need to change.
"""
import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()
