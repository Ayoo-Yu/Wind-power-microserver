#!/usr/bin/env bash
set -euo pipefail

# 收敛云端重复云南处理服务。默认只输出预检结果，传入 --apply 才执行变更。
umask 077
PRIMARY_SERVICE="${ECMWF_PRIMARY_SERVICE:-ecmwf-yunnan-processor.service}"
LEGACY_SERVICE="${ECMWF_LEGACY_SERVICE:-ecmwf-processor-yunnan.service}"
WATCH_DIR="${ECMWF_WATCH_DIR:-/ECMWF/yunnan_test}"
TARGET_HEALTH_SCRIPT="${ECMWF_TARGET_HEALTH_SCRIPT:-/ECMWF/health_check.sh}"
BACKUP_ROOT="${ECMWF_BACKUP_ROOT:-/root/ecmwf-maintenance-backups}"
SOURCE_HEALTH_SCRIPT=""
SOURCE_ROLLBACK_SCRIPT=""
APPLY=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply)
            APPLY=true
            shift
            ;;
        --health-script)
            SOURCE_HEALTH_SCRIPT="$2"
            shift 2
            ;;
        --rollback-script)
            SOURCE_ROLLBACK_SCRIPT="$2"
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
if [ -z "${SOURCE_HEALTH_SCRIPT}" ] || [ ! -f "${SOURCE_HEALTH_SCRIPT}" ]; then
    printf '必须通过 --health-script 提供新版巡检脚本。\n' >&2
    exit 1
fi
bash -n "${SOURCE_HEALTH_SCRIPT}"
if [ -n "${SOURCE_ROLLBACK_SCRIPT}" ]; then
    bash -n "${SOURCE_ROLLBACK_SCRIPT}"
fi

primary_active="$(systemctl is-active "${PRIMARY_SERVICE}" || true)"
primary_enabled="$(systemctl is-enabled "${PRIMARY_SERVICE}" || true)"
legacy_active="$(systemctl is-active "${LEGACY_SERVICE}" || true)"
legacy_enabled="$(systemctl is-enabled "${LEGACY_SERVICE}" || true)"
incoming_count="$(find "${WATCH_DIR}" -maxdepth 1 -type f ! -name '*.idx' | wc -l)"
process_count="$(pgrep -fc '[e]cmwf_processor_process_yunnan_test.py' || true)"

printf '主服务: %s, enabled=%s, active=%s\n' "${PRIMARY_SERVICE}" "${primary_enabled}" "${primary_active}"
printf '旧服务: %s, enabled=%s, active=%s\n' "${LEGACY_SERVICE}" "${legacy_enabled}" "${legacy_active}"
printf '云南处理进程数: %s\n' "${process_count}"
printf '接收目录待处理文件数: %s\n' "${incoming_count}"

if [ "${primary_active}" != "active" ]; then
    printf '主服务当前未运行，停止维护。\n' >&2
    exit 1
fi
if [ "${incoming_count}" -ne 0 ]; then
    printf '接收目录存在待处理文件，停止维护。\n' >&2
    exit 1
fi
if command -v lsof >/dev/null 2>&1 && lsof +D "${WATCH_DIR}" 2>/dev/null | grep -q 'ecmwf_processor'; then
    printf '处理进程正在打开接收目录文件，停止维护。\n' >&2
    exit 1
fi

if [ "${APPLY}" != true ]; then
    printf '预检通过。传入 --apply 后将备份配置、停用旧服务并替换巡检脚本。\n'
    exit 0
fi

timestamp="$(date '+%Y%m%d_%H%M%S')"
backup_dir="${BACKUP_ROOT}/${timestamp}"
mkdir -p "${backup_dir}"
cp -a "/etc/systemd/system/${PRIMARY_SERVICE}" "${backup_dir}/"
cp -a "/etc/systemd/system/${LEGACY_SERVICE}" "${backup_dir}/"
cp -a "${TARGET_HEALTH_SCRIPT}" "${backup_dir}/health_check.sh"
if [ -n "${SOURCE_ROLLBACK_SCRIPT}" ]; then
    install -m 0755 "${SOURCE_ROLLBACK_SCRIPT}" "${backup_dir}/rollback.sh"
fi
printf '%s\n' "${primary_active}" >"${backup_dir}/primary.active"
printf '%s\n' "${primary_enabled}" >"${backup_dir}/primary.enabled"
printf '%s\n' "${legacy_active}" >"${backup_dir}/legacy.active"
printf '%s\n' "${legacy_enabled}" >"${backup_dir}/legacy.enabled"

rollback() {
    printf '执行回滚，备份目录: %s\n' "${backup_dir}" >&2
    cp -a "${backup_dir}/${PRIMARY_SERVICE}" "/etc/systemd/system/${PRIMARY_SERVICE}"
    cp -a "${backup_dir}/${LEGACY_SERVICE}" "/etc/systemd/system/${LEGACY_SERVICE}"
    cp -a "${backup_dir}/health_check.sh" "${TARGET_HEALTH_SCRIPT}"
    systemctl daemon-reload
    if [ "${primary_enabled}" = "enabled" ]; then systemctl enable "${PRIMARY_SERVICE}"; fi
    if [ "${legacy_enabled}" = "enabled" ]; then systemctl enable "${LEGACY_SERVICE}"; fi
    if [ "${primary_active}" = "active" ]; then systemctl start "${PRIMARY_SERVICE}"; fi
    if [ "${legacy_active}" = "active" ]; then systemctl start "${LEGACY_SERVICE}"; fi
}
trap rollback ERR

install -m 0755 "${SOURCE_HEALTH_SCRIPT}" "${TARGET_HEALTH_SCRIPT}.new"
mv -f "${TARGET_HEALTH_SCRIPT}.new" "${TARGET_HEALTH_SCRIPT}"
systemctl stop "${LEGACY_SERVICE}"
systemctl disable "${LEGACY_SERVICE}"
systemctl enable "${PRIMARY_SERVICE}"
sleep 2

if ! systemctl is-active --quiet "${PRIMARY_SERVICE}"; then
    printf '主服务在收敛后未运行。\n' >&2
    false
fi
if systemctl is-active --quiet "${LEGACY_SERVICE}"; then
    printf '旧服务在收敛后仍运行。\n' >&2
    false
fi
final_process_count="$(pgrep -fc '[e]cmwf_processor_process_yunnan_test.py' || true)"
if [ "${final_process_count}" -ne 1 ]; then
    printf '收敛后进程数为 %s，期望 1。\n' "${final_process_count}" >&2
    false
fi
bash "${TARGET_HEALTH_SCRIPT}"

trap - ERR
printf '服务收敛完成。备份目录: %s\n' "${backup_dir}"
