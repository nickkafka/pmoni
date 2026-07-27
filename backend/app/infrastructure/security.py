from cryptography.fernet import Fernet, InvalidToken


class CredentialProtectionUnavailable(RuntimeError):
    pass


class FernetCredentialCipher:
    def __init__(self, key: str | None) -> None:
        if not key:
            raise CredentialProtectionUnavailable(
                "DEVICE_CREDENTIALS_KEY deve ser configurada antes do cadastro de dispositivos."
            )
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise CredentialProtectionUnavailable("Não foi possível descriptografar a credencial.") from exc
