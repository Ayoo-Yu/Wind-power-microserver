"""应用凭据的对称加密工具。"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Mapping, Optional

from cryptography.fernet import Fernet, InvalidToken


ENCRYPTED_PREFIX = "enc:v1:"
MINIMUM_KEY_LENGTH = 32
_PLACEHOLDER_PARTS = ("change-me", "replace-me", "example", "password")


class CredentialCipherError(RuntimeError):
    """凭据加解密基础异常。"""


class CredentialConfigurationError(CredentialCipherError):
    """凭据加密密钥配置异常。"""


class CredentialDecryptionError(CredentialCipherError):
    """凭据无法使用当前密钥解密。"""


def _read_key_file(path_value: str) -> str:
    path = Path(path_value).expanduser()
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CredentialConfigurationError(
            f"无法读取 CREDENTIAL_ENCRYPTION_KEY_FILE: {path}"
        ) from exc


def resolve_encryption_secret(environ: Optional[Mapping[str, str]] = None) -> str:
    """读取并校验独立的凭据加密密钥。"""

    env = environ if environ is not None else os.environ
    direct_value = (env.get("CREDENTIAL_ENCRYPTION_KEY") or "").strip()
    file_path = (env.get("CREDENTIAL_ENCRYPTION_KEY_FILE") or "").strip()

    if direct_value and file_path:
        raise CredentialConfigurationError(
            "CREDENTIAL_ENCRYPTION_KEY 与 CREDENTIAL_ENCRYPTION_KEY_FILE 不能同时设置"
        )

    secret = direct_value or (_read_key_file(file_path) if file_path else "")
    if not secret:
        raise CredentialConfigurationError(
            "未配置 CREDENTIAL_ENCRYPTION_KEY 或 CREDENTIAL_ENCRYPTION_KEY_FILE"
        )
    if len(secret) < MINIMUM_KEY_LENGTH:
        raise CredentialConfigurationError(
            f"CREDENTIAL_ENCRYPTION_KEY 长度至少需要 {MINIMUM_KEY_LENGTH} 个字符"
        )

    lowered = secret.lower()
    if any(part in lowered for part in _PLACEHOLDER_PARTS):
        raise CredentialConfigurationError("CREDENTIAL_ENCRYPTION_KEY 仍为示例值")
    return secret


def _build_fernet(environ: Optional[Mapping[str, str]] = None) -> Fernet:
    secret = resolve_encryption_secret(environ)
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(derived_key)


def is_encrypted_secret(value: object) -> bool:
    """判断值是否使用当前密文封装格式。"""

    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)


def has_secret(value: object) -> bool:
    """判断数据库字段是否已经保存有效凭据。"""

    return isinstance(value, str) and bool(value.strip())


def encrypt_secret(
    value: Optional[str],
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """加密单个凭据，已加密值保持不变。"""

    if value is None or value == "":
        return value
    if not isinstance(value, str):
        raise TypeError("凭据必须为字符串")
    if is_encrypted_secret(value):
        decrypt_secret(value, environ)
        return value

    token = _build_fernet(environ).encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(
    value: Optional[str],
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """解密单个凭据，并兼容迁移前的明文值。"""

    if value is None or value == "":
        return value
    if not isinstance(value, str):
        raise TypeError("凭据必须为字符串")
    if not is_encrypted_secret(value):
        return value

    token = value[len(ENCRYPTED_PREFIX) :]
    try:
        return _build_fernet(environ).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, TypeError, ValueError) as exc:
        raise CredentialDecryptionError(
            "凭据解密失败，请核对 CREDENTIAL_ENCRYPTION_KEY"
        ) from exc
