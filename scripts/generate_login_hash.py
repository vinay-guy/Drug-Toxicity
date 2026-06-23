#!/usr/bin/env python3
"""Generate a PBKDF2-SHA256 salted password hash compatible with src/app.py

Usage:
  python scripts/generate_login_hash.py
  or
  python scripts/generate_login_hash.py mypassword

Outputs a single line: salt_hex:hash_hex
"""
import os
import sys
import hashlib
import getpass


def make_password_hash(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + dk.hex()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pwd = sys.argv[1]
    else:
        pwd = getpass.getpass("Password: ")
    print(make_password_hash(pwd))
