"""DQYC E 文本的离线校验、分层保存与五场站适配。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
TAG_PATTERN = re.compile(
    r"^<(?P<report_type>[A-Za-z0-9_]+)::(?P<entity>[^ ]+) "
    r"Date='(?P<date>\d{4}-\d{2}-\d{2})' "
    r"Time='(?P<time>\d{2}-\d{2}-\d{2})'>$"
)
FEATURE_PATTERN = re.compile(
    r"^(?P<variable>[A-Za-z0-9]+)_"
    r"(?P<latitude>-?\d+(?:\.\d+)?)_"
    r"(?P<longitude>-?\d+(?:\.\d+)?)$"
)
FILENAME_PATTERN = re.compile(
    r"^YCSJ_YN\.ZhuYXDC_DQYC_(?P<date>\d{8})_(?P<time>\d{6})\.dat$"
)


class NwpETextValidationError(ValueError):
    """DQYC 文件违反版本化输入契约。"""


def _coordinate(value: object) -> str:
    """将坐标规范化为稳定字符串。"""

    normalized = Decimal(str(value)).normalize()
    text = format(normalized, "f")
    return text if "." in text else f"{text}.0"


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _aware_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING_TZ)
    return value.astimezone(BEIJING_TZ)


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_text(path: Path, content: str) -> None:
    _atomic_write_bytes(path, content.encode("utf-8"))


@dataclass(frozen=True)
class FarmGrid:
    code: str
    name: str
    latitudes: tuple[str, ...]
    longitudes: tuple[str, ...]

    @property
    def points(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (latitude, longitude)
            for latitude in self.latitudes
            for longitude in self.longitudes
        )


@dataclass(frozen=True)
class NwpETextContract:
    schema_version: str
    report_type: str
    entity: str
    interval_minutes: int
    model_steps: int
    regulatory_steps: int
    default_cycle_offset_minutes: int
    variables: tuple[str, ...]
    farms: tuple[FarmGrid, ...]

    @classmethod
    def load(cls, path: str | Path) -> "NwpETextContract":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        required = {
            "schema_version",
            "report_type",
            "entity",
            "interval_minutes",
            "model_steps",
            "regulatory_steps",
            "default_cycle_offset_minutes",
            "variables",
            "farms",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise NwpETextValidationError(
                f"NWP E 文本契约缺少字段: {', '.join(missing)}"
            )

        farms = tuple(
            FarmGrid(
                code=str(code).upper(),
                name=str(config["name"]),
                latitudes=tuple(_coordinate(value) for value in config["latitudes"]),
                longitudes=tuple(
                    _coordinate(value) for value in config["longitudes"]
                ),
            )
            for code, config in raw["farms"].items()
        )
        contract = cls(
            schema_version=str(raw["schema_version"]),
            report_type=str(raw["report_type"]),
            entity=str(raw["entity"]),
            interval_minutes=int(raw["interval_minutes"]),
            model_steps=int(raw["model_steps"]),
            regulatory_steps=int(raw["regulatory_steps"]),
            default_cycle_offset_minutes=int(raw["default_cycle_offset_minutes"]),
            variables=tuple(str(item) for item in raw["variables"]),
            farms=farms,
        )
        contract.validate_definition()
        return contract

    def validate_definition(self) -> None:
        if self.interval_minutes <= 0:
            raise NwpETextValidationError("interval_minutes 必须大于零")
        if self.model_steps <= 0:
            raise NwpETextValidationError("model_steps 必须大于零")
        if self.regulatory_steps < self.model_steps:
            raise NwpETextValidationError(
                "regulatory_steps 不能小于 model_steps"
            )
        if len(self.variables) != len(set(self.variables)):
            raise NwpETextValidationError("variables 存在重复项")
        codes = [farm.code for farm in self.farms]
        if len(codes) != len(set(codes)):
            raise NwpETextValidationError("场站编码存在重复项")

    @property
    def unique_points(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                {point for farm in self.farms for point in farm.points},
                key=lambda point: (Decimal(point[0]), Decimal(point[1])),
            )
        )

    @property
    def expected_features(self) -> frozenset[str]:
        return frozenset(self.expected_feature_order)

    @property
    def expected_feature_order(self) -> tuple[str, ...]:
        return tuple(
            f"{variable}_{latitude}_{longitude}"
            for variable in self.variables
            for latitude, longitude in self.unique_points
        )


@dataclass(frozen=True)
class NwpETextDocument:
    source_path: Path
    source_bytes: bytes
    source_sha256: str
    prefix_lines: tuple[str, ...]
    header_line: str
    closing_line: str
    report_type: str
    entity: str
    tagged_time: datetime
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    timestamps: tuple[datetime, ...]

    @property
    def feature_headers(self) -> tuple[str, ...]:
        return self.headers[1:]

    @property
    def horizon_hours(self) -> float:
        if len(self.timestamps) < 2:
            return 0.0
        return (
            self.timestamps[-1] - self.timestamps[0]
        ).total_seconds() / 3600.0

    def summary(self, contract: NwpETextContract) -> dict[str, object]:
        return {
            "schema_version": contract.schema_version,
            "source_path": str(self.source_path),
            "source_sha256": self.source_sha256,
            "report_type": self.report_type,
            "entity": self.entity,
            "rows": len(self.rows),
            "columns": len(self.headers),
            "feature_columns": len(self.feature_headers),
            "unique_grid_points": len(contract.unique_points),
            "variables": len(contract.variables),
            "first_timestamp": _timestamp_text(self.timestamps[0]),
            "last_timestamp": _timestamp_text(self.timestamps[-1]),
            "span_hours": self.horizon_hours,
            "model_compatible": len(self.rows) >= contract.model_steps,
            "regulatory_240h_ready": len(self.rows) >= contract.regulatory_steps,
        }


@dataclass(frozen=True)
class ShadowAdaptationResult:
    raw_path: Path
    model_path: Path
    manifest_path: Path
    business_paths: dict[str, Path]
    summary: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            **self.summary,
            "raw_path": str(self.raw_path),
            "model_path": str(self.model_path),
            "manifest_path": str(self.manifest_path),
            "business_paths": {
                code: str(path) for code, path in self.business_paths.items()
            },
        }


def read_etext(path: str | Path) -> NwpETextDocument:
    source_path = Path(path).resolve()
    source_bytes = source_path.read_bytes()
    try:
        text = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NwpETextValidationError("DQYC 文件必须使用 UTF-8 编码") from exc

    lines = text.splitlines()
    if len(lines) < 6:
        raise NwpETextValidationError("DQYC 文件行数不足")
    if not lines[0].startswith("<!System=") or "Code=UTF-8" not in lines[0]:
        raise NwpETextValidationError("DQYC 系统头缺少 UTF-8 声明")

    tag_index = next(
        (index for index, line in enumerate(lines) if TAG_PATTERN.fullmatch(line)),
        None,
    )
    if tag_index is None:
        raise NwpETextValidationError("DQYC 起始标签无效")
    match = TAG_PATTERN.fullmatch(lines[tag_index])
    assert match is not None
    tagged_time = datetime.strptime(
        f"{match.group('date')} {match.group('time')}", "%Y-%m-%d %H-%M-%S"
    ).replace(tzinfo=BEIJING_TZ)

    header_index = next(
        (index for index, line in enumerate(lines) if line.startswith("@\t")),
        None,
    )
    if header_index is None:
        raise NwpETextValidationError("DQYC 文件缺少表头")
    headers = tuple(lines[header_index][2:].split("\t"))
    if not headers or headers[0] != "Timestamp":
        raise NwpETextValidationError("DQYC 第一列必须为 Timestamp")
    if len(headers) != len(set(headers)):
        raise NwpETextValidationError("DQYC 表头存在重复列")

    closing_line = f"</{match.group('report_type')}::{match.group('entity')}>"
    closing_index = next(
        (
            index
            for index in range(header_index + 1, len(lines))
            if lines[index] == closing_line
        ),
        None,
    )
    if closing_index is None:
        raise NwpETextValidationError("DQYC 文件缺少结束标签")

    rows: list[tuple[str, ...]] = []
    timestamps: list[datetime] = []
    for line_number, line in enumerate(
        lines[header_index + 1 : closing_index], start=header_index + 2
    ):
        if not line.startswith("#\t"):
            raise NwpETextValidationError(
                f"DQYC 第 {line_number} 行缺少数据标记"
            )
        values = tuple(line[2:].split("\t"))
        if len(values) != len(headers):
            raise NwpETextValidationError(
                f"DQYC 第 {line_number} 行列数为 {len(values)}，"
                f"期望 {len(headers)}"
            )
        try:
            timestamp = datetime.strptime(
                values[0], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=BEIJING_TZ)
        except ValueError as exc:
            raise NwpETextValidationError(
                f"DQYC 第 {line_number} 行时间格式无效: {values[0]}"
            ) from exc
        for column_number, value in enumerate(values[1:], start=2):
            try:
                number = float(value)
            except ValueError as exc:
                raise NwpETextValidationError(
                    f"DQYC 第 {line_number} 行第 {column_number} 列含非数值"
                ) from exc
            if not math.isfinite(number):
                raise NwpETextValidationError(
                    f"DQYC 第 {line_number} 行第 {column_number} 列含无效数值"
                )
        rows.append(values)
        timestamps.append(timestamp)

    if not rows:
        raise NwpETextValidationError("DQYC 文件没有数据行")

    return NwpETextDocument(
        source_path=source_path,
        source_bytes=source_bytes,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        prefix_lines=tuple(lines[:header_index]),
        header_line=lines[header_index],
        closing_line=closing_line,
        report_type=match.group("report_type"),
        entity=match.group("entity"),
        tagged_time=tagged_time,
        headers=headers,
        rows=tuple(rows),
        timestamps=tuple(timestamps),
    )


def validate_etext(
    document: NwpETextDocument,
    contract: NwpETextContract,
    *,
    require_model_steps: bool = True,
) -> dict[str, object]:
    if document.report_type != contract.report_type:
        raise NwpETextValidationError(
            f"报表类型为 {document.report_type}，期望 {contract.report_type}"
        )
    if document.entity != contract.entity:
        raise NwpETextValidationError(
            f"实体为 {document.entity}，期望 {contract.entity}"
        )
    if document.timestamps[0] != document.tagged_time:
        raise NwpETextValidationError("DQYC 标签时间与第一条数据时间不一致")

    filename_match = FILENAME_PATTERN.fullmatch(document.source_path.name)
    if filename_match is None:
        raise NwpETextValidationError("DQYC 文件名不符合生产命名契约")
    filename_time = datetime.strptime(
        filename_match.group("date") + filename_match.group("time"),
        "%Y%m%d%H%M%S",
    ).replace(tzinfo=BEIJING_TZ)
    if filename_time != document.tagged_time:
        raise NwpETextValidationError("DQYC 文件名时间与标签时间不一致")

    expected_delta = timedelta(minutes=contract.interval_minutes)
    for previous, current in zip(document.timestamps, document.timestamps[1:]):
        if current - previous != expected_delta:
            raise NwpETextValidationError(
                "DQYC 时间序列必须严格按 "
                f"{contract.interval_minutes} 分钟连续递增"
            )

    actual_features = frozenset(document.feature_headers)
    missing = sorted(contract.expected_features - actual_features)
    unexpected = sorted(actual_features - contract.expected_features)
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"缺少 {len(missing)} 列")
        if unexpected:
            details.append(f"多出 {len(unexpected)} 列")
        raise NwpETextValidationError(
            "DQYC 特征列与契约不一致: " + "，".join(details)
        )
    if document.feature_headers != contract.expected_feature_order:
        raise NwpETextValidationError("DQYC 特征列顺序与生产契约不一致")

    for header in document.feature_headers:
        match = FEATURE_PATTERN.fullmatch(header)
        if match is None:
            raise NwpETextValidationError(f"DQYC 特征列名称无效: {header}")
        if match.group("variable") not in contract.variables:
            raise NwpETextValidationError(
                f"DQYC 出现未纳管变量: {match.group('variable')}"
            )

    if require_model_steps and len(document.rows) < contract.model_steps:
        raise NwpETextValidationError(
            f"DQYC 只有 {len(document.rows)} 个时刻，"
            f"模型契约要求至少 {contract.model_steps} 个"
        )
    return document.summary(contract)


def _shifted_rows(
    document: NwpETextDocument,
    effective_start: datetime,
) -> tuple[tuple[str, ...], ...]:
    offset = effective_start - document.timestamps[0]
    return tuple(
        (_timestamp_text(timestamp + offset), *row[1:])
        for timestamp, row in zip(document.timestamps, document.rows)
    )


def _render_etext(
    document: NwpETextDocument,
    rows: Sequence[Sequence[str]],
) -> bytes:
    first = datetime.strptime(rows[0][0], "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=BEIJING_TZ
    )
    prefix = list(document.prefix_lines)
    for index, line in enumerate(prefix):
        if TAG_PATTERN.fullmatch(line):
            prefix[index] = (
                f"<{document.report_type}::{document.entity} "
                f"Date='{first:%Y-%m-%d}' Time='{first:%H-%M-%S}'>"
            )
            break
    lines = [*prefix, document.header_line]
    lines.extend("#\t" + "\t".join(row) for row in rows)
    lines.append(document.closing_line)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _feature_indices(
    document: NwpETextDocument,
) -> dict[tuple[str, str, str], int]:
    indices: dict[tuple[str, str, str], int] = {}
    for index, header in enumerate(document.headers):
        match = FEATURE_PATTERN.fullmatch(header)
        if match is None:
            continue
        indices[
            (
                match.group("variable"),
                _coordinate(match.group("latitude")),
                _coordinate(match.group("longitude")),
            )
        ] = index
    return indices


def _write_business_csv(
    path: Path,
    *,
    document: NwpETextDocument,
    contract: NwpETextContract,
    farm: FarmGrid,
    rows: Sequence[Sequence[str]],
    forecast_source: datetime,
) -> int:
    indices = _feature_indices(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    record_count = 0
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(
                [
                    "forecast_source",
                    "forecast_time",
                    "latitude",
                    "longitude",
                    *contract.variables,
                ]
            )
            for row in rows:
                forecast_time = datetime.strptime(
                    row[0], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=BEIJING_TZ)
                for latitude, longitude in farm.points:
                    values = [
                        row[indices[(variable, latitude, longitude)]]
                        for variable in contract.variables
                    ]
                    writer.writerow(
                        [
                            forecast_source.isoformat(),
                            forecast_time.isoformat(),
                            latitude,
                            longitude,
                            *values,
                        ]
                    )
                    record_count += 1
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return record_count


def adapt_etext_to_shadow(
    input_path: str | Path,
    output_root: str | Path,
    contract: NwpETextContract,
    *,
    replay_start: datetime | None = None,
    forecast_source: datetime | None = None,
) -> ShadowAdaptationResult:
    document = read_etext(input_path)
    summary = validate_etext(document, contract)
    root = Path(output_root).resolve()

    effective_start = (
        _aware_local(replay_start)
        if replay_start is not None
        else document.timestamps[0]
    )
    effective_rows = _shifted_rows(document, effective_start)
    source_cycle = (
        _aware_local(forecast_source)
        if forecast_source is not None
        else effective_start
        - timedelta(minutes=contract.default_cycle_offset_minutes)
    )

    identity = document.source_sha256[:16]
    effective_key = effective_start.strftime("%Y%m%dT%H%M%S")
    raw_path = root / "raw" / identity / document.source_path.name
    if raw_path.exists() and hashlib.sha256(raw_path.read_bytes()).hexdigest() != document.source_sha256:
        raise NwpETextValidationError(f"原始层文件内容冲突: {raw_path}")
    if not raw_path.exists():
        _atomic_write_bytes(raw_path, document.source_bytes)

    model_rows = effective_rows[: contract.model_steps]
    model_name = (
        "YCSJ_YN.ZhuYXDC_DQYC_"
        f"{effective_start:%Y%m%d_%H%M%S}.dat"
    )
    model_path = root / "model" / effective_key / model_name
    model_content = _render_etext(document, model_rows)
    if model_path.exists() and model_path.read_bytes() != model_content:
        raise NwpETextValidationError(f"模型视图文件内容冲突: {model_path}")
    if not model_path.exists():
        _atomic_write_bytes(model_path, model_content)

    business_paths: dict[str, Path] = {}
    business_counts: dict[str, int] = {}
    for farm in contract.farms:
        output_name = (
            f"nwp_{farm.code}_{effective_key}_{identity}.csv"
        )
        output_path = root / "business" / farm.code / output_name
        if not output_path.exists():
            count = _write_business_csv(
                output_path,
                document=document,
                contract=contract,
                farm=farm,
                rows=effective_rows,
                forecast_source=source_cycle,
            )
        else:
            count = len(effective_rows) * len(farm.points)
        business_paths[farm.code] = output_path
        business_counts[farm.code] = count

    result_summary = {
        **summary,
        "effective_first_timestamp": _timestamp_text(effective_start),
        "effective_last_timestamp": effective_rows[-1][0],
        "forecast_source": source_cycle.isoformat(),
        "replay_applied": replay_start is not None,
        "model_rows": len(model_rows),
        "business_rows": business_counts,
    }
    manifest = {
        **result_summary,
        "source_filename": document.source_path.name,
        "raw_path": str(raw_path),
        "model_path": str(model_path),
        "business_paths": {
            code: str(path) for code, path in business_paths.items()
        },
    }
    manifest_path = root / "manifests" / f"{identity}_{effective_key}.json"
    _atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return ShadowAdaptationResult(
        raw_path=raw_path,
        model_path=model_path,
        manifest_path=manifest_path,
        business_paths=business_paths,
        summary=result_summary,
    )


def _synthetic_value(variable: str, step: int, point_index: int) -> str:
    phase = step / 24.0 + point_index / 11.0
    wind = 5.0 + 2.0 * math.sin(phase)
    values = {
        "100u": wind * 0.72,
        "100v": wind * 0.69,
        "10u": wind * 0.55,
        "10v": wind * 0.52,
        "200u": wind * 0.88,
        "200v": wind * 0.84,
        "2d": 282.0 + 3.0 * math.sin(phase / 2.0),
        "2t": 285.0 + 4.0 * math.sin(phase / 2.0),
        "dsrp": max(0.0, 500.0 * math.sin((step % 96) / 96.0 * math.pi)),
        "gh": 1500.0 + point_index * 2.0,
        "hcc": 0.4 + 0.2 * math.sin(phase),
        "msl": 100800.0 + 350.0 * math.cos(phase / 3.0),
        "skt": 286.0 + 4.5 * math.sin(phase / 2.0),
        "sp": 87000.0 + 250.0 * math.cos(phase / 3.0),
        "ssrc": max(0.0, 420.0 * math.sin((step % 96) / 96.0 * math.pi)),
        "ssrd": max(0.0, 520.0 * math.sin((step % 96) / 96.0 * math.pi)),
        "tcc": 0.5 + 0.25 * math.sin(phase),
        "tcwv": 22.0 + 5.0 * math.sin(phase / 4.0),
        "tisr": max(0.0, 680.0 * math.sin((step % 96) / 96.0 * math.pi)),
    }
    value = values.get(variable, step * 0.01 + point_index * 0.001)
    return format(value, ".8f")


def write_synthetic_etext(
    path: str | Path,
    contract: NwpETextContract,
    *,
    start: datetime,
    steps: int | None = None,
) -> Path:
    output_path = Path(path).resolve()
    effective_start = _aware_local(start).replace(second=0, microsecond=0)
    row_count = steps if steps is not None else contract.model_steps
    if row_count <= 0:
        raise NwpETextValidationError("合成 DQYC 行数必须大于零")

    features = [
        f"{variable}_{latitude}_{longitude}"
        for variable in contract.variables
        for latitude, longitude in contract.unique_points
    ]
    lines = [
        "<!System=OMS Version=1.0 Code=UTF-8 Data=1.0!>",
        f"// {contract.report_type} 预测数据 (实体: {contract.entity})",
        f"<{contract.report_type}::{contract.entity} "
        f"Date='{effective_start:%Y-%m-%d}' Time='{effective_start:%H-%M-%S}'>",
        "@\tTimestamp\t" + "\t".join(features),
    ]
    points = contract.unique_points
    for step in range(row_count):
        timestamp = effective_start + timedelta(
            minutes=contract.interval_minutes * step
        )
        values = [
            _synthetic_value(variable, step, point_index)
            for variable in contract.variables
            for point_index, _point in enumerate(points)
        ]
        lines.append(
            "#\t" + _timestamp_text(timestamp) + "\t" + "\t".join(values)
        )
    lines.append(f"</{contract.report_type}::{contract.entity}>")
    _atomic_write_text(output_path, "\n".join(lines) + "\n")
    return output_path


def ceil_quarter(value: datetime) -> datetime:
    local = _aware_local(value).replace(second=0, microsecond=0)
    remainder = local.minute % 15
    if remainder == 0:
        return local
    return local + timedelta(minutes=15 - remainder)


def iter_stable_etext_files(
    input_dir: str | Path,
    *,
    minimum_age_seconds: float,
) -> Iterable[Path]:
    now = datetime.now().timestamp()
    for path in sorted(Path(input_dir).glob("YCSJ_*_DQYC_*.dat")):
        try:
            if now - path.stat().st_mtime >= minimum_age_seconds:
                yield path
        except OSError:
            continue
