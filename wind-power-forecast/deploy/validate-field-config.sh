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
if [ "${REPORT_SCHEDULER_MODE:-}" != "celery" ]; then
    error "REPORT_SCHEDULER_MODE 必须为 celery"
fi

require_secret DB_PASSWORD 16
require_secret SECRET_KEY 32
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
