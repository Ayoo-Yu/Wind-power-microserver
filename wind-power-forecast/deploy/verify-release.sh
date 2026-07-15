#!/usr/bin/env bash
set -euo pipefail

RELEASE_DIR="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$RELEASE_DIR"

if [ ! -f SHA256SUMS ]; then
    echo "错误：缺少 SHA256SUMS"
    exit 1
fi

echo "正在校验离线发布包完整性"
sha256sum -c SHA256SUMS

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
