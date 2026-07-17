#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env}"
ERROR_COUNT=0

error() {
    echo "配置错误：$*" >&2
    ERROR_COUNT=$((ERROR_COUNT + 1))
}

is_true() {
    [ "${1:-false}" = "true" ]
}

require_secret() {
    local name="$1"
    local value="${!name:-}"
    local minimum="$2"
    if [ -z "$value" ]; then
        error "$name 不能为空"
        return
    fi
    case "$value" in
        *change-me*|*CHANGE_ME*|password|admin|secret)
            error "$name 仍为示例值"
            return
            ;;
    esac
    if [ "${#value}" -lt "$minimum" ]; then
        error "$name 长度至少需要 $minimum 个字符"
    fi
}

require_versioned_image() {
    local name="$1"
    local value="${!name:-}"
    if [ -z "$value" ]; then
        error "$name 不能为空"
        return
    fi
    case "$value" in
        *:latest|latest)
            error "$name 必须使用固定版本标签"
            ;;
    esac
}

require_absolute_path() {
    local name="$1"
    local value="${!name:-}"
    if [ -z "$value" ]; then
        error "$name 不能为空"
        return
    fi
    case "$value" in
        /*) ;;
        *) error "$name 必须使用 Linux 绝对路径" ;;
    esac
}

if [ ! -f "$ENV_FILE" ]; then
    echo "配置错误：找不到环境文件 $ENV_FILE" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [ "${DEPLOYMENT_MODE:-}" != "field" ]; then
    error "DEPLOYMENT_MODE 必须为 field"
fi
if [ "${DB_SCHEMA_STRICT:-false}" != "true" ]; then
    error "DB_SCHEMA_STRICT 必须为 true"
fi
if [ "${MODEL_AUTO_APPROVAL_ENABLED:-true}" != "false" ]; then
    error "场站模式必须关闭模型自动审批"
fi
case "${DB_SCHEMA_ACTION:-}" in
    prepare|upgrade|check) ;;
    *) error "DB_SCHEMA_ACTION 仅支持 prepare、upgrade 或 check" ;;
esac

actual_fallback_age="${ACTUAL_POWER_RAW_FALLBACK_MAX_AGE_SECONDS:-900}"
case "$actual_fallback_age" in
    ''|*[!0-9]*)
        error "ACTUAL_POWER_RAW_FALLBACK_MAX_AGE_SECONDS 必须是整数"
        ;;
    *)
        if [ "$actual_fallback_age" -lt 1 ] || [ "$actual_fallback_age" -gt 900 ]; then
            error "ACTUAL_POWER_RAW_FALLBACK_MAX_AGE_SECONDS 必须在 1 至 900 之间"
        fi
        ;;
esac
case "${ACTUAL_POWER_TURBINE_SOURCE_UNIT:-kW}" in
    kW|kw|MW|mw) ;;
    *) error "ACTUAL_POWER_TURBINE_SOURCE_UNIT 仅支持 kW 或 MW" ;;
esac

require_secret DB_PASSWORD 16
require_secret SECRET_KEY 32
require_absolute_path DATA_ROOT
if [ -n "${CREDENTIAL_ENCRYPTION_KEY:-}" ] && [ -n "${CREDENTIAL_ENCRYPTION_KEY_FILE:-}" ]; then
    error "CREDENTIAL_ENCRYPTION_KEY 与 CREDENTIAL_ENCRYPTION_KEY_FILE 不能同时设置"
elif [ -n "${CREDENTIAL_ENCRYPTION_KEY:-}" ]; then
    require_secret CREDENTIAL_ENCRYPTION_KEY 32
elif [ -z "${CREDENTIAL_ENCRYPTION_KEY_FILE:-}" ]; then
    error "必须设置 CREDENTIAL_ENCRYPTION_KEY 或 CREDENTIAL_ENCRYPTION_KEY_FILE"
fi
if [ -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    require_secret BOOTSTRAP_ADMIN_PASSWORD 16
fi
if [ -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ] && [ -n "${BOOTSTRAP_ADMIN_PASSWORD_FILE:-}" ]; then
    error "BOOTSTRAP_ADMIN_PASSWORD 与 BOOTSTRAP_ADMIN_PASSWORD_FILE 不能同时设置"
fi
require_versioned_image FRONTEND_IMAGE
require_versioned_image PREDICTION_IMAGE
require_versioned_image DATABASE_IMAGE

if is_true "${SCADA_REQUIRED:-false}" && ! is_true "${SCADA_REALTIME_ENABLED:-false}"; then
    error "SCADA_REQUIRED=true 时必须启用 SCADA_REALTIME_ENABLED"
fi
if is_true "${SCADA_REALTIME_ENABLED:-false}"; then
    require_secret SCADA_WORKER_SECRET 24
    if [ -z "${SCADA_ALLOWED_NETWORKS:-}" ]; then
        error "启用 SCADA 后必须设置 SCADA_ALLOWED_NETWORKS"
    fi
fi

if is_true "${NWP_INGESTION_REQUIRED:-false}" && ! is_true "${NWP_INGESTION_ENABLED:-false}"; then
    error "NWP_INGESTION_REQUIRED=true 时必须启用 NWP_INGESTION_ENABLED"
fi

if is_true "${INTEGRATION_API_REQUIRED:-false}" && ! is_true "${INTEGRATION_API_ENABLED:-false}"; then
    error "INTEGRATION_API_REQUIRED=true 时必须启用 INTEGRATION_API_ENABLED"
fi
if is_true "${INTEGRATION_API_ENABLED:-false}"; then
    require_secret INTEGRATION_API_TOKEN 32
fi

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "场站配置校验失败，共 $ERROR_COUNT 项。" >&2
    exit 1
fi

echo "场站配置校验通过。"
