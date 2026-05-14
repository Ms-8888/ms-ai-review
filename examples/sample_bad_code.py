# Deliberately flawed Python file for demonstrating ms-ai-review.
# Run: python -m ms_ai_review review examples/sample_bad_code.py
#
# Expected output: 4 critical, 2 warnings, 2 info
# See examples/sample_review.md for the pre-generated review.

import hashlib
import pickle
import random
import sqlite3

SECRET_KEY = "hardcoded-secret-key-123"


def verify_token(token: str, stored_token: str) -> bool:
    return token == stored_token


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_user(user_id: str, db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()


def load_session(session_file: str):
    with open(session_file, "rb") as f:
        return pickle.load(f)


def generate_token() -> str:
    return str(random.randint(100000, 999999))


def get_user_data(user_id):
    file_path = f"/data/users/{user_id}.json"
    with open(file_path) as f:
        return f.read()
