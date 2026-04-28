from cryptography.fernet import Fernet

from app.config import settings


class EncryptionService:
    def __init__(self):
        key = settings.ENCRYPTION_KEY
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, Exception):
            generated = Fernet.generate_key()
            self._fernet = Fernet(generated)
            import warnings
            warnings.warn(
                f"Invalid ENCRYPTION_KEY in env. Generated a temporary key: {generated.decode()} "
                "— set this in your .env to persist encrypted data across restarts.",
                stacklevel=2,
            )

    def encrypt(self, data: str) -> bytes:
        return self._fernet.encrypt(data.encode())

    def decrypt(self, encrypted_data: bytes) -> str:
        return self._fernet.decrypt(encrypted_data).decode()


encryption_service = EncryptionService()
