#!/usr/bin/env python3
"""Create a random admin account and write models/.auth.json

Outputs the username and plaintext password to stdout for the user.
"""
import os
import json
import secrets
import hashlib

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
MODEL_DIR = os.path.join(REPO_ROOT, "models")
AUTH_FILE = os.path.join(MODEL_DIR, ".auth.json")

if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR, exist_ok=True)

username = "admin" + secrets.token_hex(2)
password = secrets.token_urlsafe(12)

# pbkdf2-hash compatible with src/app.py
salt = secrets.token_bytes(16)
dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
pw_hash = salt.hex() + ":" + dk.hex()

with open(AUTH_FILE, "w", encoding="utf-8") as fh:
    json.dump({"username": username, "password_hash": pw_hash}, fh)

print("WROTE:", AUTH_FILE)
print("USERNAME:", username)
print("PASSWORD:", password)
print("Keep these credentials safe. You can log in via the app.")
