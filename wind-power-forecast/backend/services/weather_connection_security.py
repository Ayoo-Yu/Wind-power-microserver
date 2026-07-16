"""气象连接凭据的统一读写边界。"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from utils.credential_cipher import decrypt_secret, encrypt_secret, has_secret


SECRET_FIELDS = ("password", "key_passphrase")


def apply_connection_secrets(connection: Any, data: Mapping[str, Any]) -> None:
    """将新增凭据加密写入连接对象，空值表示保留原配置。"""

    for field in SECRET_FIELDS:
        clear_field = f"clear_{field}"
        if data.get(clear_field) is True:
            setattr(connection, field, None)
            continue

        value = data.get(field)
        if isinstance(value, str) and value:
            setattr(connection, field, encrypt_secret(value))


def build_connection_config(connection: Any) -> Dict[str, Any]:
    """生成仅供 SSH 调用使用的明文连接配置。"""

    return {
        "host": connection.host,
        "port": connection.port,
        "username": connection.username,
        "auth_type": connection.auth_type,
        "password": decrypt_secret(connection.password),
        "private_key_path": connection.private_key_path,
        "key_passphrase": decrypt_secret(connection.key_passphrase),
    }


def serialize_connection_secret_state(connection: Any) -> Dict[str, bool]:
    """生成可以安全返回前端的凭据状态。"""

    return {
        "password_set": has_secret(connection.password),
        "key_passphrase_set": has_secret(connection.key_passphrase),
    }
