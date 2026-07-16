"""管理员引导和人工重置密码的安全读取与校验。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


MIN_ADMIN_PASSWORD_LENGTH = 16
_REJECTED_PASSWORDS = {
    "12345678ab",
    "admin",
    "admin123",
    "changeme",
    "change-me",
    "password",
    "secret",
}


class AdminPasswordConfigurationError(ValueError):
    """管理员密码配置缺失、冲突或不符合最低安全要求。"""


def validate_admin_password(password: str) -> str:
    """校验管理员密码并返回原值，避免调用方重复处理。"""

    if not isinstance(password, str) or not password:
        raise AdminPasswordConfigurationError("管理员密码不能为空")
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise AdminPasswordConfigurationError(
            f"管理员密码长度至少需要 {MIN_ADMIN_PASSWORD_LENGTH} 个字符"
        )
    if password.strip().lower() in _REJECTED_PASSWORDS or "change-me" in password.lower():
        raise AdminPasswordConfigurationError("管理员密码仍为默认值或示例值")
    return password


def load_admin_password(
    value_env: str,
    file_env: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """从环境变量或 UTF-8 密码文件读取密码，两种来源只能选择一种。"""

    source = os.environ if environ is None else environ
    value = str(source.get(value_env, "") or "")
    file_name = str(source.get(file_env, "") or "").strip()

    if value and file_name:
        raise AdminPasswordConfigurationError(
            f"{value_env} 与 {file_env} 不能同时设置"
        )
    if file_name:
        path = Path(file_name)
        try:
            value = path.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as exc:
            raise AdminPasswordConfigurationError(
                f"无法读取管理员密码文件 {path}: {exc}"
            ) from exc
    if not value:
        raise AdminPasswordConfigurationError(
            f"请设置 {value_env}，或通过 {file_env} 提供 UTF-8 密码文件"
        )
    return validate_admin_password(value)
