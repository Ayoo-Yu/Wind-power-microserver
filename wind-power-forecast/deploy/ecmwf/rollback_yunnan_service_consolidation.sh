#!/usr/bin/env bash
set -euo pipefail

# 根据维护备份恢复两个云南处理服务和原巡检脚本。
PRIMARY_SERVICE="${ECMWF_PRIMARY_SERVICE:-ecmwf-yunnan-processor.service}"
LEGACY_SERVICE="${ECMWF_LEGACY_SERVICE:-ecmwf-processor-yunnan.service}"
TARGET_HEALTH_SCRIPT="${ECMWF_TARGET_HEALTH_SCRIPT:-/ECMWF/health_check.sh}"
BACKUP_ROOT="${ECMWF_BACKUP_ROOT:-/root/ecmwf-maintenance-backups}"
BACKUP_DIR=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        *)
            printf '未知参数: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    printf '必须使用 root 执行。\n' >&2
    exit 1
fi
if [ -z "${BACKUP_DIR}" ] || [ ! -d "${BACKUP_DIR}" ]; then
    printf '必须通过 --backup-dir 提供有效备份目录。\n' >&2
    exit 1
fi

resolved_root="$(readlink -f "${BACKUP_ROOT}")"
resolved_backup="$(readlink -f "${BACKUP_DIR}")"
case "${resolved_backup}" in
    "${resolved_root}"/*) ;;
    *)
        printf '备份目录必须位于 %s 内。\n' "${resolved_root}" >&2
        exit 1
        ;;
esac

for required in \
    "${PRIMARY_SERVICE}" \
    "${LEGACY_SERVICE}" \
    health_check.sh \
    primary.active \
    primary.enabled \
    legacy.active \
    legacy.enabled; do
    if [ ! -f "${resolved_backup}/${required}" ]; then
        printf '备份缺少文件: %s\n' "${required}" >&2
        exit 1
    fi
done

primary_active="$(<"${resolved_backup}/primary.active")"
primary_enabled="$(<"${resolved_backup}/primary.enabled")"
legacy_active="$(<"${resolved_backup}/legacy.active")"
legacy_enabled="$(<"${resolved_backup}/legacy.enabled")"

systemctl stop "${PRIMARY_SERVICE}" "${LEGACY_SERVICE}" || true
systemctl disable "${PRIMARY_SERVICE}" "${LEGACY_SERVICE}" || true
cp -a "${resolved_backup}/${PRIMARY_SERVICE}" "/etc/systemd/system/${PRIMARY_SERVICE}"
cp -a "${resolved_backup}/${LEGACY_SERVICE}" "/etc/systemd/system/${LEGACY_SERVICE}"
install -m 0755 "${resolved_backup}/health_check.sh" "${TARGET_HEALTH_SCRIPT}.rollback"
mv -f "${TARGET_HEALTH_SCRIPT}.rollback" "${TARGET_HEALTH_SCRIPT}"
systemctl daemon-reload

if [ "${primary_enabled}" = "enabled" ]; then
    systemctl enable "${PRIMARY_SERVICE}"
fi
if [ "${legacy_enabled}" = "enabled" ]; then
    systemctl enable "${LEGACY_SERVICE}"
fi
if [ "${primary_active}" = "active" ]; then
    systemctl start "${PRIMARY_SERVICE}"
fi
if [ "${legacy_active}" = "active" ]; then
    systemctl start "${LEGACY_SERVICE}"
fi

printf '回滚完成，来源备份: %s\n' "${resolved_backup}"
printf '主服务: enabled=%s, active=%s\n' \
    "$(systemctl is-enabled "${PRIMARY_SERVICE}" || true)" \
    "$(systemctl is-active "${PRIMARY_SERVICE}" || true)"
printf '旧服务: enabled=%s, active=%s\n' \
    "$(systemctl is-enabled "${LEGACY_SERVICE}" || true)" \
    "$(systemctl is-active "${LEGACY_SERVICE}" || true)"
