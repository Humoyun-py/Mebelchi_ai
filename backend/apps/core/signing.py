"""Short-lived signed URLs so <img>/<a> tags can load private files without headers."""
from django.core import signing

SALT = "mebelchi.file"
MAX_AGE = 60 * 15


def sign_file(kind: str, pk: int) -> str:
    return signing.dumps({"k": kind, "id": pk}, salt=SALT)


def verify_file(token: str, kind: str, pk: int) -> bool:
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return False
    return data.get("k") == kind and data.get("id") == pk
