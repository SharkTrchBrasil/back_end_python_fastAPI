# src/core/encryption.py
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64
from src.core.config import config


class EncryptionService:
    """Serviço de criptografia AES-256"""

    def __init__(self):
        # ✅ VALIDAÇÃO DE SEGURANÇA
        key_bytes = config.ENCRYPTION_KEY.encode()

        if len(key_bytes) < 32:
            raise ValueError(
                f"❌ ENCRYPTION_KEY insegura! Precisa de 32+ bytes, tem {len(key_bytes)}. "
                f"Gere uma nova com: python generate_encryption_key.py"
            )

        # Chave deve ter 32 bytes para AES-256
        self.key = key_bytes[:32]

    def encrypt(self, plaintext: str) -> bytes:
        """Criptografa uma string"""
        if not plaintext:
            return None

        cipher = AES.new(self.key, AES.MODE_GCM)
        nonce = cipher.nonce
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())

        # Retorna: nonce + tag + ciphertext
        return base64.b64encode(nonce + tag + ciphertext)

    def decrypt(self, encrypted: bytes) -> str:
        """Descriptografa bytes"""
        if not encrypted:
            return None

        data = base64.b64decode(encrypted)
        nonce = data[:16]
        tag = data[16:32]
        ciphertext = data[32:]

        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)

        return plaintext.decode()


# Singleton
encryption_service = EncryptionService()