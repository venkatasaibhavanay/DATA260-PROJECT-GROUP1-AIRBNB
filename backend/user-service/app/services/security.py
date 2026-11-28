"""Password hashing (bcrypt) and the API doc's password policy."""
import re

import bcrypt

PASSWORD_RULE = "Password must be at least 8 characters with one letter and one digit."


def password_problem(password: str) -> str | None:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return PASSWORD_RULE
    if len(password.encode("utf-8")) > 72:
        return "Password must be at most 72 bytes."
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("ascii"))
    except ValueError:
        return False


# Used to keep login timing similar when the email does not exist.
DUMMY_HASH = hash_password("dummy-password-1")
