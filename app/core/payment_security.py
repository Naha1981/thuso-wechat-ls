import hashlib,hmac

def verify_hmac(raw: bytes, signature: str|None, secret: str) -> bool:
    if not signature or not secret: return False
    value=signature.removeprefix('sha256=')
    expected=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    return hmac.compare_digest(value,expected)
