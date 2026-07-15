"""SCADA 连接目标的场站网段访问策略。"""

from __future__ import annotations

import ipaddress
import socket
from typing import Mapping


class ScadaNetworkPolicyError(ValueError):
    """连接目标不符合部署网段白名单。"""


def _setting(config: Mapping | None, name: str, default: str = "") -> str:
    if config is not None and hasattr(config, "get"):
        value = config.get(name, default)
    else:
        import os
        value = os.environ.get(name, default)
    return str(value or "").strip()


def validate_scada_target(host: str, config: Mapping | None = None) -> list[str]:
    """解析目标地址并确认全部结果都位于显式允许的场站网段。"""

    host = str(host or "").strip()
    if not host:
        raise ScadaNetworkPolicyError("SCADA 目标地址不能为空")
    deployment_mode = _setting(config, "DEPLOYMENT_MODE", "development").lower()
    raw_networks = _setting(config, "SCADA_ALLOWED_NETWORKS")
    networks = []
    for item in raw_networks.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError as exc:
            raise ScadaNetworkPolicyError(f"SCADA_ALLOWED_NETWORKS 包含无效网段: {item}") from exc

    try:
        addresses = sorted({
            item[4][0]
            for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        })
    except socket.gaierror as exc:
        raise ScadaNetworkPolicyError(f"无法解析 SCADA 目标地址: {host}") from exc
    if not addresses:
        raise ScadaNetworkPolicyError(f"SCADA 目标地址没有解析结果: {host}")

    if "169.254.169.254" in addresses:
        raise ScadaNetworkPolicyError("SCADA 目标地址禁止访问云平台元数据服务")

    if not networks and deployment_mode in {"development", "test"}:
        return addresses
    if not networks:
        raise ScadaNetworkPolicyError("现场模式必须配置 SCADA_ALLOWED_NETWORKS")

    rejected = []
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if not any(parsed in network for network in networks):
            rejected.append(address)
    if rejected:
        raise ScadaNetworkPolicyError(
            f"SCADA 目标地址不在允许网段: {', '.join(rejected)}"
        )
    return addresses
