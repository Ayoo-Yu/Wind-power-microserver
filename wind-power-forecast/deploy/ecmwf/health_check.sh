#!/usr/bin/env bash
set -uo pipefail

# 云端 DQYC 每日只读巡检。systemd 负责进程自动恢复，本脚本负责发现异常。
ECMWF_ROOT="${ECMWF_ROOT:-/ECMWF}"
OUTPUT_DIR="${ECMWF_OUTPUT_DIR:-${ECMWF_ROOT}/yunnan_test_processed_csv}"
LOG_FILE="${ECMWF_HEALTH_LOG:-${ECMWF_ROOT}/logs/health_check.log}"
PYTHON_BIN="${ECMWF_PYTHON_BIN:-/root/anaconda3/envs/ecmwf_env/bin/python}"
PRIMARY_SERVICE="${ECMWF_PRIMARY_SERVICE:-ecmwf-yunnan-processor.service}"
LEGACY_SERVICE="${ECMWF_LEGACY_SERVICE:-ecmwf-processor-yunnan.service}"
EXPECTED_ROWS="${ECMWF_MODEL_ROWS:-508}"
EXPECTED_COLUMNS="${ECMWF_DQYC_COLUMNS:-1046}"
LOCK_FILE="${ECMWF_HEALTH_LOCK:-/var/lock/ecmwf-dqyc-health.lock}"

mkdir -p "$(dirname "${LOG_FILE}")"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    exit 0
fi

log() {
    printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" "$2" >>"${LOG_FILE}"
}

failed=0
log "INFO" "开始 DQYC 每日巡检"

if systemctl is-active --quiet "${PRIMARY_SERVICE}"; then
    log "OK" "主处理服务正在运行: ${PRIMARY_SERVICE}"
else
    log "ERROR" "主处理服务未运行: ${PRIMARY_SERVICE}"
    failed=1
fi

if systemctl is-active --quiet "${LEGACY_SERVICE}"; then
    log "ERROR" "检测到旧云南处理服务仍在运行: ${LEGACY_SERVICE}"
    failed=1
else
    log "OK" "旧云南处理服务处于停止状态"
fi

process_count="$(pgrep -fc '[e]cmwf_processor_process_yunnan_test.py' || true)"
if [ "${process_count}" -eq 1 ]; then
    log "OK" "云南处理进程数量为 1"
else
    log "ERROR" "云南处理进程数量为 ${process_count}，期望 1"
    failed=1
fi

target_date="$(TZ=Asia/Shanghai date -d 'yesterday' '+%Y%m%d')"
year="${target_date:0:4}"
month_day="${target_date:4:4}"
batch_id="${year}_${month_day}1800"
batch_dir="${OUTPUT_DIR}/${batch_id}"

if [ ! -d "${batch_dir}" ]; then
    log "ERROR" "18 时批次目录不存在: ${batch_dir}"
    failed=1
else
    dqyc_file="$(find "${batch_dir}" -maxdepth 1 -type f -name 'YCSJ_YN.ZhuYXDC_DQYC_*.dat' -print -quit)"
    if [ -z "${dqyc_file}" ]; then
        log "ERROR" "18 时批次缺少 DQYC: ${batch_id}"
        failed=1
    elif validation="$("${PYTHON_BIN}" - "${dqyc_file}" "${EXPECTED_ROWS}" "${EXPECTED_COLUMNS}" <<'PY'
import datetime as dt
import json
import math
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
expected_rows = int(sys.argv[2])
expected_columns = int(sys.argv[3])
lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
header = next((line for line in lines if line.startswith("@\t")), None)
if header is None:
    raise SystemExit("缺少表头")
headers = header[2:].split("\t")
if len(headers) != expected_columns:
    raise SystemExit(f"列数为 {len(headers)}，期望 {expected_columns}")
if headers[0] != "Timestamp" or len(headers) != len(set(headers)):
    raise SystemExit("Timestamp 或重复列检查失败")

variables = (
    "100u", "100v", "10u", "10v", "200u", "200v", "2d", "2t",
    "dsrp", "gh", "hcc", "msl", "skt", "sp", "ssrc", "ssrd",
    "tcc", "tcwv", "tisr",
)
farm_grids = (
    (("26.0", "26.1", "26.2"), ("103.2", "103.3", "103.4", "103.5")),
    (("25.7", "25.8", "25.9", "26.0"), ("103.2", "103.3", "103.4")),
    (("24.0", "24.1", "24.2", "24.3"), ("103.0", "103.1", "103.2", "103.3")),
    (("25.2", "25.3", "25.4"), ("103.3", "103.4", "103.5")),
    (("23.8", "23.9", "24.0", "24.1", "24.2"), ("103.2", "103.3", "103.4")),
)
points = sorted(
    {
        (latitude, longitude)
        for latitudes, longitudes in farm_grids
        for latitude in latitudes
        for longitude in longitudes
    },
    key=lambda point: (float(point[0]), float(point[1])),
)
expected_headers = [
    "Timestamp",
    *(
        f"{variable}_{latitude}_{longitude}"
        for variable in variables
        for latitude, longitude in points
    ),
]
if len(expected_headers) != expected_columns:
    raise SystemExit("巡检契约列数配置不一致")
if headers != expected_headers:
    raise SystemExit("DQYC 特征列或顺序与生产契约不一致")

rows = [line[2:].split("\t") for line in lines if line.startswith("#\t")]
if len(rows) < expected_rows:
    raise SystemExit(f"数据行数为 {len(rows)}，至少需要 {expected_rows}")
timestamps = []
for row_number, row in enumerate(rows, start=1):
    if len(row) != expected_columns:
        raise SystemExit(f"第 {row_number} 行列数异常")
    try:
        timestamp = dt.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise SystemExit(f"第 {row_number} 行时间无效: {exc}")
    timestamps.append(timestamp)
    for value in row[1:]:
        try:
            number = float(value)
        except ValueError:
            raise SystemExit(f"第 {row_number} 行含非数值")
        if not math.isfinite(number):
            raise SystemExit(f"第 {row_number} 行含无效数值")

expected_delta = dt.timedelta(minutes=15)
if any(current - previous != expected_delta for previous, current in zip(timestamps, timestamps[1:])):
    raise SystemExit("时间序列没有按 15 分钟连续递增")

name_match = re.fullmatch(
    r"YCSJ_YN\.ZhuYXDC_DQYC_(\d{8})_(\d{6})\.dat", path.name
)
if name_match is None:
    raise SystemExit("文件名不符合 DQYC 生产契约")
name_time = dt.datetime.strptime("".join(name_match.groups()), "%Y%m%d%H%M%S")
if name_time != timestamps[0]:
    raise SystemExit("文件名时间与首行时间不一致")

print(
    json.dumps(
        {
            "rows": len(rows),
            "columns": len(headers),
            "first": timestamps[0].isoformat(sep=" "),
            "last": timestamps[-1].isoformat(sep=" "),
        },
        ensure_ascii=False,
    )
)
PY
)"; then
        log "OK" "DQYC 校验通过: ${batch_id} ${validation}"
    else
        log "ERROR" "DQYC 校验失败: ${batch_id} ${validation}"
        failed=1
    fi
fi

if [ "${failed}" -eq 0 ]; then
    log "INFO" "DQYC 每日巡检通过"
else
    log "ERROR" "DQYC 每日巡检失败"
fi

exit "${failed}"
