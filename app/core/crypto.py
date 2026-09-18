from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretCipher:
    """Application-level envelope encryption for integration secrets."""

    def __init__(self, encoded_key: str) -> None:
        if not encoded_key:
            raise RuntimeError("SECRETS_ENCRYPTION_KEY is not configured")
        try:
            key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
        except Exception as exc:
            raise RuntimeError("SECRETS_ENCRYPTION_KEY must be URL-safe base64") from exc
        if len(key) != 32:
            raise RuntimeError("SECRETS_ENCRYPTION_KEY must decode to exactly 32 bytes")
        self._key = key

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return "v1:" + ":".join(
            [
                base64.urlsafe_b64encode(nonce).decode("ascii"),
                base64.urlsafe_b64encode(ciphertext).decode("ascii"),
            ]
        )

    def decrypt(self, payload: str) -> str:
        try:
            version, nonce_b64, ciphertext_b64 = payload.split(":", 2)
            if version != "v1":
                raise ValueError("unsupported secret version")
            nonce = base64.urlsafe_b64decode(nonce_b64.encode("ascii"))
            ciphertext = base64.urlsafe_b64decode(ciphertext_b64.encode("ascii"))
            return AESGCM(self._key).decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception as exc:
            raise RuntimeError("Unable to decrypt integration secret") from exc
