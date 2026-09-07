import hashlib, hmac
from app.core.security import verify_meta_signature

def test_signature():
    body=b'{}'; secret='abc'
    sig='sha256='+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    verify_meta_signature(body,sig,secret)
