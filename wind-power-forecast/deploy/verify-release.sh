#!/usr/bin/env bash
set -euo pipefail

RELEASE_DIR="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$RELEASE_DIR"

if [ ! -f SHA256SUMS ]; then
    echo "错误：缺少 SHA256SUMS"
    exit 1
fi

if [ ! -f release-manifest.json ] || [ ! -f application-sbom.cdx.json ]; then
    echo "错误：发布包缺少清单或 SBOM"
    exit 1
fi

echo "正在校验离线发布包完整性"
sha256sum -c SHA256SUMS

if ! command -v python3 >/dev/null 2>&1; then
    echo "错误：发布策略校验需要 Python 3"
    exit 1
fi

python3 - <<'PY'
import json
from pathlib import Path

manifest = json.loads(Path("release-manifest.json").read_text(encoding="utf-8"))
sbom = json.loads(Path("application-sbom.cdx.json").read_text(encoding="utf-8"))
if manifest.get("schema_version") != "1.1":
    raise SystemExit("错误：发布清单版本不受支持")
if manifest.get("source", {}).get("dirty"):
    raise SystemExit("错误：正式场站拒绝带未提交改动的发布包")
if manifest.get("sbom", {}).get("path") != "application-sbom.cdx.json":
    raise SystemExit("错误：发布清单未声明应用 SBOM")
if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.5":
    raise SystemExit("错误：SBOM 格式或版本无效")
for name, reference in manifest.get("images", {}).items():
    reference = str(reference or "")
    if not reference or reference.endswith(":latest") or (":" not in reference and "@sha256:" not in reference):
        raise SystemExit(f"错误：镜像 {name} 未使用固定版本标签")
PY

if [ "${REQUIRE_RELEASE_SIGNATURE:-false}" = "true" ] && [ ! -f SHA256SUMS.sig ]; then
    echo "错误：当前场站策略要求发布包数字签名"
    exit 1
fi

if [ -f SHA256SUMS.sig ]; then
    if [ ! -f release-signing-public.pem ]; then
        echo "错误：发布包含签名，但缺少公钥"
        exit 1
    fi
    if ! command -v openssl >/dev/null 2>&1; then
        echo "错误：校验签名需要 OpenSSL"
        exit 1
    fi
    openssl dgst -sha256 \
        -verify release-signing-public.pem \
        -signature SHA256SUMS.sig \
        SHA256SUMS
fi

echo "发布包校验通过"
