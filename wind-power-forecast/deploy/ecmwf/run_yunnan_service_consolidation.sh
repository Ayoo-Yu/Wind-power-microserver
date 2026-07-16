#!/usr/bin/env bash
set -euo pipefail

# 编排预检、备份、服务收敛和变更后验证。默认仅执行预检。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY_SCRIPT="${SCRIPT_DIR}/apply_yunnan_service_consolidation.sh"
HEALTH_SCRIPT="${SCRIPT_DIR}/health_check.sh"
ROLLBACK_SCRIPT="${SCRIPT_DIR}/rollback_yunnan_service_consolidation.sh"
PRIMARY_SERVICE="${ECMWF_PRIMARY_SERVICE:-ecmwf-yunnan-processor.service}"
LEGACY_SERVICE="${ECMWF_LEGACY_SERVICE:-ecmwf-processor-yunnan.service}"
WATCH_DIR="${ECMWF_WATCH_DIR:-/ECMWF/yunnan_test}"
OUTPUT_DIR="${ECMWF_OUTPUT_DIR:-/ECMWF/yunnan_test_processed_csv}"
TARGET_HEALTH_SCRIPT="${ECMWF_TARGET_HEALTH_SCRIPT:-/ECMWF/health_check.sh}"
HEALTH_LOG="${ECMWF_HEALTH_LOG:-/ECMWF/logs/health_check.log}"
APPLY=false

if [ "${1:-}" = "--apply" ]; then
    APPLY=true
    shift
fi
if [ "$#" -ne 0 ]; then
    printf '仅支持可选参数 --apply。\n' >&2
    exit 2
fi

for script in "${APPLY_SCRIPT}" "${HEALTH_SCRIPT}" "${ROLLBACK_SCRIPT}"; do
    bash -n "${script}"
done

printf '预检时间: %s\n' "$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S %Z')"
bash "${APPLY_SCRIPT}" \
    --health-script "${HEALTH_SCRIPT}" \
    --rollback-script "${ROLLBACK_SCRIPT}"

if [ "${APPLY}" != true ]; then
    printf '预检完成，未修改服务器。\n'
    exit 0
fi

latest_dqyc="$(
    find "${OUTPUT_DIR}" -type f -name 'YCSJ_YN.ZhuYXDC_DQYC_*.dat' \
        -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-
)"
if [ -z "${latest_dqyc}" ]; then
    printf '没有找到可用于变更保护的 DQYC 文件。\n' >&2
    exit 1
fi

before_dqyc_sha="$(sha256sum "${latest_dqyc}" | cut -d' ' -f1)"
before_cron_sha="$(crontab -l 2>/dev/null | sha256sum | cut -d' ' -f1)"
before_primary_pid="$(
    systemctl show -p MainPID "${PRIMARY_SERVICE}" | cut -d= -f2
)"

apply_output="$(
    bash "${APPLY_SCRIPT}" \
        --apply \
        --health-script "${HEALTH_SCRIPT}" \
        --rollback-script "${ROLLBACK_SCRIPT}"
)"
printf '%s\n' "${apply_output}"
backup_line="${apply_output##*$'\n'}"
backup_dir="${backup_line##*: }"

test -d "${backup_dir}"
test -x "${backup_dir}/rollback.sh"

rollback_after_verification_failure() {
    printf '变更后验证失败，执行备份回滚: %s\n' "${backup_dir}" >&2
    bash "${backup_dir}/rollback.sh" --backup-dir "${backup_dir}"
}
trap rollback_after_verification_failure ERR

test "$(systemctl is-active "${PRIMARY_SERVICE}")" = "active"
test "$(systemctl is-enabled "${PRIMARY_SERVICE}")" = "enabled"
if systemctl is-active --quiet "${LEGACY_SERVICE}"; then
    printf '旧服务在收敛后仍处于运行状态。\n' >&2
    exit 1
fi
if systemctl is-enabled --quiet "${LEGACY_SERVICE}"; then
    printf '旧服务在收敛后仍处于启用状态。\n' >&2
    exit 1
fi
test "$(pgrep -fc '[e]cmwf_processor_process_yunnan_test.py')" -eq 1
test "$(find "${WATCH_DIR}" -maxdepth 1 -type f ! -name '*.idx' | wc -l)" -eq 0
test "$(sha256sum "${latest_dqyc}" | cut -d' ' -f1)" = "${before_dqyc_sha}"
test "$(crontab -l 2>/dev/null | sha256sum | cut -d' ' -f1)" = "${before_cron_sha}"
test "$(sha256sum "${TARGET_HEALTH_SCRIPT}" | cut -d' ' -f1)" = \
    "$(sha256sum "${HEALTH_SCRIPT}" | cut -d' ' -f1)"
test "$(systemctl show -p MainPID "${PRIMARY_SERVICE}" | cut -d= -f2)" = \
    "${before_primary_pid}"
trap - ERR

printf '验证时间: %s\n' "$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S %Z')"
printf '主服务状态: enabled=%s, active=%s, pid=%s\n' \
    "$(systemctl is-enabled "${PRIMARY_SERVICE}")" \
    "$(systemctl is-active "${PRIMARY_SERVICE}")" \
    "$(systemctl show -p MainPID "${PRIMARY_SERVICE}" | cut -d= -f2)"
printf '旧服务状态: enabled=%s, active=%s\n' \
    "$(systemctl is-enabled "${LEGACY_SERVICE}" || true)" \
    "$(systemctl is-active "${LEGACY_SERVICE}" || true)"
printf '云南处理进程数: %s\n' \
    "$(pgrep -fc '[e]cmwf_processor_process_yunnan_test.py')"
printf 'DQYC 摘要保持不变: %s  %s\n' "${before_dqyc_sha}" "${latest_dqyc}"
printf 'root 定时任务摘要保持不变: %s\n' "${before_cron_sha}"
printf '备份目录: %s\n' "${backup_dir}"
tail -n 12 "${HEALTH_LOG}"
