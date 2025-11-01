# src/core/encryption.py
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64
from src.core.config import config


class EncryptionService:
    """Serviço de criptografia AES-256"""

    def __init__(self):
        # ✅ CORREÇÃO: Inicialização lazy - valida apenas quando necessário
        self._key = None
        self._initialized = False

    def _ensure_initialized(self):
        """Garante que o serviço está inicializado antes de usar"""
        if self._initialized:
            return
        
        # ✅ CORREÇÃO: Permite inicialização mesmo sem ENCRYPTION_KEY para migrations
        # Usa uma chave dummy apenas para evitar erro de inicialização
        if not config.ENCRYPTION_KEY:
            # Chave dummy de 32 bytes para permitir inicialização sem config
            # Esta chave NÃO deve ser usada para criptografar dados reais
            self._key = b'dummy_key_for_migrations_only_32bytes!!'
            self._initialized = True
            return
        
        # ✅ VALIDAÇÃO DE SEGURANÇA quando a chave está presente
        key_bytes = config.ENCRYPTION_KEY.encode()

        if len(key_bytes) < 32:
            raise ValueError(
                f"❌ ENCRYPTION_KEY insegura! Precisa de 32+ bytes, tem {len(key_bytes)}. "
                f"Gere uma nova com: python generate_encryption_key.py"
            )

        # Chave deve ter 32 bytes para AES-256
        self._key = key_bytes[:32]
        self._initialized = True

    def encrypt(self, plaintext: str) -> bytes:
        """Criptografa uma string"""
        if not plaintext:
            return None

        self._ensure_initialized()
        
        # ✅ Valida se está usando chave real (não dummy)
        if not config.ENCRYPTION_KEY:
            raise ValueError(
                "❌ ENCRYPTION_KEY não configurada. Não é possível criptografar dados reais."
            )

        cipher = AES.new(self._key, AES.MODE_GCM)
        nonce = cipher.nonce
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())

        # Retorna: nonce + tag + ciphertext
        return base64.b64encode(nonce + tag + ciphertext)

    def decrypt(self, encrypted: bytes) -> str:
        """Descriptografa bytes"""
        if not encrypted:
            return None

        self._ensure_initialized()
        
        # ✅ Valida se está usando chave real (não dummy)
        if not config.ENCRYPTION_KEY:
            raise ValueError(
                "❌ ENCRYPTION_KEY não configurada. Não é possível descriptografar dados reais."
            )

        data = base64.b64decode(encrypted)
        nonce = data[:16]
        tag = data[16:32]
        ciphertext = data[32:]

        cipher = AES.new(self._key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)

        return plaintext.decode()


# ✅ CORREÇÃO: Singleton lazy - não falha na inicialização
encryption_service = EncryptionService()