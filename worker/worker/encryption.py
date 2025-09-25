import json
from cryptography.fernet import Fernet
from .config import settings


class CredentialEncryption:
    def __init__(self):
        # Use the secret key to derive a Fernet key
        key = settings.secret_key.encode()[:32].ljust(32, b'0')  # Ensure 32 bytes
        from base64 import urlsafe_b64encode
        self.fernet = Fernet(urlsafe_b64encode(key))

    def encrypt_credentials(self, credentials: dict) -> bytes:
        """Encrypt credential dictionary to bytes"""
        json_str = json.dumps(credentials)
        return self.fernet.encrypt(json_str.encode())

    def decrypt_credentials(self, encrypted_data: bytes) -> dict:
        """Decrypt bytes back to credential dictionary"""
        decrypted_str = self.fernet.decrypt(encrypted_data).decode()
        return json.loads(decrypted_str)


credential_encryption = CredentialEncryption()