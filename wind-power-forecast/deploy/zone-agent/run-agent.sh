#!/usr/bin/env sh
set -eu

CONFIG_FILE="${ZONE_AGENT_CONFIG:-/etc/windpower-zone-agent.env}"
if [ -r "$CONFIG_FILE" ]; then
    set -a
    . "$CONFIG_FILE"
    set +a
fi

: "${AGENT_SOURCE:?AGENT_SOURCE 未配置}"
: "${AGENT_FARM_CODE:?AGENT_FARM_CODE 未配置}"
: "${AGENT_DATA_TYPE:?AGENT_DATA_TYPE 未配置}"

AGENT_SPOOL="${AGENT_SPOOL:-/var/lib/windpower-zone-agent/spool}"
AGENT_TARGET_MODE="${AGENT_TARGET_MODE:-http}"
AGENT_POLL_SECONDS="${AGENT_POLL_SECONDS:-2}"
AGENT_RETRY_BASE_SECONDS="${AGENT_RETRY_BASE_SECONDS:-5}"
AGENT_RETRY_MAX_SECONDS="${AGENT_RETRY_MAX_SECONDS:-300}"

if [ -n "${INTEGRATION_API_TOKEN_FILE:-}" ] && [ -r "$INTEGRATION_API_TOKEN_FILE" ]; then
    INTEGRATION_API_TOKEN="$(tr -d '\r\n' < "$INTEGRATION_API_TOKEN_FILE")"
    export INTEGRATION_API_TOKEN
fi

run_transfer() {
    if [ "$AGENT_TARGET_MODE" = "directory" ]; then
        : "${AGENT_TARGET_SPOOL:?AGENT_TARGET_SPOOL 未配置}"
        python3 -m integration.cli "$@" \
            --spool "$AGENT_SPOOL" \
            --target-spool "$AGENT_TARGET_SPOOL" \
            --poll-seconds "$AGENT_POLL_SECONDS" \
            --retry-base-seconds "$AGENT_RETRY_BASE_SECONDS" \
            --retry-max-seconds "$AGENT_RETRY_MAX_SECONDS"
    else
        : "${AGENT_TARGET_URL:?AGENT_TARGET_URL 未配置}"
        python3 -m integration.cli "$@" \
            --spool "$AGENT_SPOOL" \
            --target-url "$AGENT_TARGET_URL" \
            --poll-seconds "$AGENT_POLL_SECONDS" \
            --retry-base-seconds "$AGENT_RETRY_BASE_SECONDS" \
            --retry-max-seconds "$AGENT_RETRY_MAX_SECONDS"
    fi
}

if [ -n "${AGENT_INPUT_DIR:-}" ]; then
    recursive_flag=""
    if [ "${AGENT_RECURSIVE:-false}" = "true" ]; then
        recursive_flag="--recursive"
    fi
    if [ -n "$recursive_flag" ]; then
        run_transfer bridge \
            --input-dir "$AGENT_INPUT_DIR" \
            --source "$AGENT_SOURCE" \
            --farm-code "$AGENT_FARM_CODE" \
            --data-type "$AGENT_DATA_TYPE" \
            --pattern "${AGENT_PATTERN:-*}" \
            --minimum-age-seconds "${AGENT_MINIMUM_AGE_SECONDS:-3}" \
            "$recursive_flag"
    else
        run_transfer bridge \
            --input-dir "$AGENT_INPUT_DIR" \
            --source "$AGENT_SOURCE" \
            --farm-code "$AGENT_FARM_CODE" \
            --data-type "$AGENT_DATA_TYPE" \
            --pattern "${AGENT_PATTERN:-*}" \
            --minimum-age-seconds "${AGENT_MINIMUM_AGE_SECONDS:-3}"
    fi
else
    run_transfer run
fi
