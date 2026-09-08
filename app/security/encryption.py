"""Encryption service for securing sensitive user data at rest."""

import base64
import hashlib
import logging
import os
import platform
import secrets
import subprocess
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger("jobot.security")

LEGACY_PREFIX = "enc:v1:"
PREFIX = "enc:v2:"


class EncryptionError(RuntimeError):
    """Raised when sensitive data cannot be safely encrypted or decrypted."""


def _get_fernet_key(raw_key: str, scope: str = "legacy") -> bytes:
    """Derive an isolated Fernet key from a master key and ownership scope."""
    key_bytes = hashlib.sha256(f"{raw_key}\0{scope}".encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


def _load_or_create_local_key() -> str:
    """Load a durable development key, creating it with owner-only permissions."""
    settings = get_settings()
    key_path = Path(settings.encryption_key_file)
    if key_path.exists():
        key = key_path.read_text(encoding="utf-8").strip()
        if key:
            return key

    if settings.env.lower() in {"production", "prod"}:
        raise EncryptionError("ENCRYPTION_KEY is required in production")

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48)
    try:
        with key_path.open("x", encoding="utf-8") as key_file:
            key_file.write(key)
        # Restrict file permissions — owner read/write only.
        # On Unix/macOS: chmod 600 (effective). On Windows: use icacls ACL.
        os.chmod(key_path, 0o600)
        if platform.system() == "Windows":
            _restrict_key_file_windows(key_path)
    except FileExistsError:
        key = key_path.read_text(encoding="utf-8").strip()
    if not key:
        raise EncryptionError(f"Encryption key file is empty: {key_path}")
    return key


def _restrict_key_file_windows(key_path: Path) -> None:
    """Apply Windows ACL to restrict encryption key file to the current user only.

    This supplements os.chmod (which is a no-op on Windows) by running icacls
    to remove inherited permissions and grant access only to the current user.
    Logs a warning if icacls is unavailable, prompting the user to set the
    ENCRYPTION_KEY environment variable explicitly.
    """
    try:
        username = os.environ.get("USERNAME") or os.environ.get("USER", "")
        key_str = str(key_path.resolve())
        # Remove inherited permissions and grant only the current user read access
        subprocess.run(
            ["icacls", key_str, "/inheritance:r", "/grant:r", f"{username}:(R)"],
            check=True,
            capture_output=True,
        )
        logger.debug("Applied Windows ACL to encryption key file: %s", key_str)
    except Exception as err:
        logger.warning(
            "Could not apply Windows ACL to encryption key file (%s). "
            "For security on Windows, set the ENCRYPTION_KEY environment variable explicitly "
            "instead of relying on the key file.",
            err,
        )


def _keyring() -> tuple[str, dict[str, str]]:
    """Return the active key ID and all configured keys available for rotation."""
    settings = get_settings()
    active_key = settings.encryption_key or _load_or_create_local_key()
    keys = {settings.encryption_key_id: active_key}
    for entry in settings.previous_encryption_keys.split(","):
        if ":" not in entry:
            continue
        key_id, raw_key = entry.split(":", 1)
        if key_id.strip() and raw_key.strip():
            keys[key_id.strip()] = raw_key.strip()
    return settings.encryption_key_id, keys


def _scope(user_id: int | None) -> str:
    """Create an explicit cryptographic boundary for global or user-owned data."""
    return f"user-{user_id}" if user_id is not None else "global"


def encrypt_text(plaintext: str | None, *, user_id: int | None = None) -> str | None:
    """Encrypt plaintext string using Fernet authenticated encryption.

    New ciphertext records the key ID and owner scope so key rotation and
    cross-account misuse can be detected without storing the master key.
    """
    if not plaintext:
        return plaintext
    if plaintext.startswith((PREFIX, LEGACY_PREFIX)):
        return plaintext

    try:
        key_id, keys = _keyring()
        scope = _scope(user_id)
        fernet = Fernet(_get_fernet_key(keys[key_id], scope))
        token = fernet.encrypt(plaintext.encode("utf-8"))
        return f"{PREFIX}{key_id}:{scope}:{token.decode('utf-8')}"
    except Exception as err:
        logger.error("Failed to encrypt sensitive data: %s", err)
        raise EncryptionError("Sensitive data could not be encrypted") from err


def decrypt_text(ciphertext: str | None, *, user_id: int | None = None) -> str | None:
    """Decrypt ciphertext string prefixed with 'enc:v1:'.

    Plaintext is accepted for legacy migration. Encrypted values fail closed
    when the key is absent, invalid, or bound to a different account.
    """
    if not ciphertext:
        return ciphertext

    try:
        _, keys = _keyring()
        if ciphertext.startswith(LEGACY_PREFIX):
            token_str = ciphertext[len(LEGACY_PREFIX):]
            active_key = keys[get_settings().encryption_key_id]
            fernet = Fernet(_get_fernet_key(active_key))
        elif ciphertext.startswith(PREFIX):
            key_id, stored_scope, token_str = ciphertext[len(PREFIX):].split(":", 2)
            expected_scope = _scope(user_id)
            if stored_scope != expected_scope or key_id not in keys:
                raise EncryptionError("Ciphertext is not available in this account or keyring")
            fernet = Fernet(_get_fernet_key(keys[key_id], stored_scope))
        else:
            return ciphertext
        decrypted_bytes = fernet.decrypt(token_str.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except EncryptionError:
        raise
    except (InvalidToken, ValueError) as err:
        logger.warning("Sensitive data decryption failed: invalid key, scope, or payload")
        raise EncryptionError("Sensitive data could not be decrypted") from err


def rotate_text(ciphertext: str | None, *, user_id: int | None = None) -> str | None:
    """Re-encrypt a value with the active key after decrypting legacy/keyring data."""
    plaintext = decrypt_text(ciphertext, user_id=user_id)
    if plaintext is None:
        return None
    if ciphertext and ciphertext.startswith(PREFIX):
        active_key_id = get_settings().encryption_key_id
        if ciphertext.startswith(f"{PREFIX}{active_key_id}:{_scope(user_id)}:"):
            return ciphertext
    return encrypt_text(plaintext, user_id=user_id)
