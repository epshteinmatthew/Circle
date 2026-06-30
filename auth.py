import time
import uuid
import json
import setup
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt

def generate_refresh_token(user_id:int) -> str:
    key = str(uuid.uuid4()).replace('-', '')[:32]
    keys = {}
    with open("refresh.json", "r") as f:
        keys = json.loads(f.read())
    keys[key] = user_id
    with open("refresh.json", "w") as f:
        f.write(json.dumps(keys))
    return key

def refresh_jwt_key(refresh: str) -> str:
    with open("refresh.json", "r") as fp:
        f = json.load(fp)
        if refresh in f.keys():
            uid = f[refresh]
            encoded_jwt = jwt.encode({'cid': setup.GOOGLE_CLIENT_ID, 'exp': time.time() + 8640, 'uid': uid},
                                     setup.GOOGLE_CLIENT_SECRET, algorithm="HS256")
            return encoded_jwt
        return "not allowed"


def validate(encoded):
    try:
        decoded = jwt.decode(encoded, setup.GOOGLE_CLIENT_SECRET, algorithms=["HS256"])
        if decoded['exp'] >= time.time() and decoded['cid'] == setup.GOOGLE_CLIENT_ID:
            return True
        else:
            return False
    except:
        return False


def validate_uid(encoded, uid:int):
    try:
        decoded = jwt.decode(encoded, setup.GOOGLE_CLIENT_SECRET, algorithms=["HS256"])
        if decoded['exp'] >= time.time() and decoded['cid'] == setup.GOOGLE_CLIENT_ID and decoded['uid'] == uid:
            return True
        else:
            return False
    except:
        return False

