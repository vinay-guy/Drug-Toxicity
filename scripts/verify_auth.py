import json, hashlib
f='models/.auth.json'
with open(f) as fh:
    data=json.load(fh)
stored=data['password_hash']
print('stored=',stored)
username=data['username']
print('username=',username)
password='cwV9eQzdjcYUVZS-'
salt_hex,hash_hex=stored.split(':')
salt=bytes.fromhex(salt_hex)
expected=bytes.fromhex(hash_hex)
dk=hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200_000)
print('match=', dk==expected)
print('dk=',dk.hex())
