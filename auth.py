import uuid
import json
import setup
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt

def generate_refresh_token() -> str:
    key = str(uuid.uuid4()).replace('-', '')[:32]
    print(key)
    keys = []
    with open("refresh.json", "r") as f:
        keys = json.loads(f.read())
    keys.append(key)
    with open("refresh.json", "w") as f:
        f.write(json.dumps(keys))
    return key

def refresh_jwt_key(refresh: str) -> str:
    with open("refresh.json", "r") as fp:
        f = json.load(fp)
        if(refresh in f):
            encoded_jwt = jwt.encode({'org':"uw.edu", 'cid': GOOGLE_CLIENT_ID, 'exp': time.time() + 86400},
                                     setup.GOOGLE_CLIENT_SECRET, algorithm="HS256")
            return encoded_jwt
        return "not allowed"


def validate(encoded):
    try:
        decoded = jwt.decode(encoded, setup.GOOGLE_CLIENT_SECRET, algorithms=["HS256"])
        if(decoded['org'] == "uw.edu" and decoded['exp'] >= time.time() and decoded['cid'] == GOOGLE_CLIENT_ID):
            return True
        else:
            return False
    except:
        return False