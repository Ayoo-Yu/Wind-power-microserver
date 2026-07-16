import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from integration.nwp_etext import (
    BEIJING_TZ,
    NwpETextContract,
    NwpETextValidationError,
    adapt_etext_to_shadow,
    read_etext,
    validate_etext,
    write_synthetic_etext,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_CONTRACT = PROJECT_ROOT / "config" / "nwp-etext-contract-v1.json"


def _small_contract(tmp_path: Path) -> NwpETextContract:
    raw = {
        "schema_version": "nwp-etext-test-v1",
        "report_type": "DQYC",
        "entity": "YN.ZhuYXDC",
        "interval_minutes": 15,
        "model_steps": 4,
        "regulatory_steps": 8,
        "default_cycle_offset_minutes": 60,
        "variables": ["100u", "100v"],
        "farms": {
            "A": {
                "name": "甲场站",
                "latitudes": [23.8],
                "longitudes": [103.2, 103.3],
            },
            "B": {
                "name": "乙场站",
                "latitudes": [23.8],
                "longitudes": [103.3],
            },
        },
    }
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return NwpETextContract.load(path)


def _sample_path(tmp_path: Path, start: datetime) -> Path:
    return tmp_path / (
        "YCSJ_YN.ZhuYXDC_DQYC_" f"{start:%Y%m%d_%H%M%S}.dat"
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_production_contract_has_observed_five_farm_shape():
    contract = NwpETextContract.load(PRODUCTION_CONTRACT)

    assert contract.model_steps == 508
    assert contract.regulatory_steps == 960
    assert len(contract.variables) == 19
    assert len(contract.unique_points) == 55
    assert len(contract.expected_features) == 1045
    assert "100u_24.0_103.2" in contract.expected_features
    assert {farm.code: len(farm.points) for farm in contract.farms} == {
        "CF": 12,
        "BNJ": 12,
        "SDS": 16,
        "DPLZ": 9,
        "ZYX": 15,
    }


def test_current_contract_preserves_raw_and_model_bytes(tmp_path):
    contract = _small_contract(tmp_path)
    start = datetime(2026, 7, 16, 19, 15, tzinfo=BEIJING_TZ)
    source = write_synthetic_etext(
        _sample_path(tmp_path, start),
        contract,
        start=start,
        steps=contract.model_steps,
    )

    result = adapt_etext_to_shadow(source, tmp_path / "shadow", contract)

    assert result.raw_path.read_bytes() == source.read_bytes()
    assert result.model_path.read_bytes() == source.read_bytes()
    assert result.summary["model_compatible"] is True
    assert result.summary["regulatory_240h_ready"] is False
    assert result.summary["model_rows"] == 4
    assert len(_read_csv(result.business_paths["A"])) == 8
    assert len(_read_csv(result.business_paths["B"])) == 4


def test_full_horizon_keeps_all_business_rows_and_crops_model_view(tmp_path):
    contract = _small_contract(tmp_path)
    start = datetime(2026, 7, 16, 19, 15, tzinfo=BEIJING_TZ)
    source = write_synthetic_etext(
        _sample_path(tmp_path, start),
        contract,
        start=start,
        steps=contract.regulatory_steps,
    )

    result = adapt_etext_to_shadow(source, tmp_path / "shadow", contract)
    model = read_etext(result.model_path)

    assert len(read_etext(result.raw_path).rows) == 8
    assert len(model.rows) == 4
    assert result.summary["regulatory_240h_ready"] is True
    assert len(_read_csv(result.business_paths["A"])) == 16
    assert len(_read_csv(result.business_paths["B"])) == 8


def test_replay_changes_effective_time_and_keeps_original_raw_file(tmp_path):
    contract = _small_contract(tmp_path)
    start = datetime(2026, 5, 4, 19, 15, tzinfo=BEIJING_TZ)
    replay_start = datetime(2026, 7, 16, 12, 0, tzinfo=BEIJING_TZ)
    source = write_synthetic_etext(
        _sample_path(tmp_path, start),
        contract,
        start=start,
        steps=contract.model_steps,
    )

    result = adapt_etext_to_shadow(
        source,
        tmp_path / "shadow",
        contract,
        replay_start=replay_start,
    )
    model = read_etext(result.model_path)
    business = _read_csv(result.business_paths["A"])

    assert result.raw_path.read_bytes() == source.read_bytes()
    assert model.timestamps[0] == replay_start
    assert model.rows[0][1:] == read_etext(source).rows[0][1:]
    assert business[0]["forecast_time"] == replay_start.isoformat()
    assert business[0]["forecast_source"] == (
        replay_start - timedelta(minutes=60)
    ).isoformat()


def test_rejects_time_gap(tmp_path):
    contract = _small_contract(tmp_path)
    start = datetime(2026, 7, 16, 19, 15, tzinfo=BEIJING_TZ)
    source = write_synthetic_etext(
        _sample_path(tmp_path, start),
        contract,
        start=start,
        steps=contract.model_steps,
    )
    text = source.read_text(encoding="utf-8")
    text = text.replace("2026-07-16 19:30:00", "2026-07-16 19:45:00", 1)
    source.write_text(text, encoding="utf-8", newline="\n")

    with pytest.raises(NwpETextValidationError, match="连续递增"):
        validate_etext(read_etext(source), contract)


def test_rejects_non_finite_value(tmp_path):
    contract = _small_contract(tmp_path)
    start = datetime(2026, 7, 16, 19, 15, tzinfo=BEIJING_TZ)
    source = write_synthetic_etext(
        _sample_path(tmp_path, start),
        contract,
        start=start,
        steps=contract.model_steps,
    )
    text = source.read_text(encoding="utf-8")
    text = text.replace("\t3.60000000", "\tNaN", 1)
    source.write_text(text, encoding="utf-8", newline="\n")

    with pytest.raises(NwpETextValidationError, match="无效数值"):
        read_etext(source)


def test_rejects_feature_order_drift(tmp_path):
    contract = _small_contract(tmp_path)
    start = datetime(2026, 7, 16, 19, 15, tzinfo=BEIJING_TZ)
    source = write_synthetic_etext(
        _sample_path(tmp_path, start),
        contract,
        start=start,
        steps=contract.model_steps,
    )
    lines = source.read_text(encoding="utf-8").splitlines()
    header_index = next(
        index for index, line in enumerate(lines) if line.startswith("@\t")
    )
    headers = lines[header_index].split("\t")
    headers[2], headers[3] = headers[3], headers[2]
    lines[header_index] = "\t".join(headers)
    source.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    with pytest.raises(NwpETextValidationError, match="列顺序"):
        validate_etext(read_etext(source), contract)


def test_rejects_non_contract_filename(tmp_path):
    contract = _small_contract(tmp_path)
    start = datetime(2026, 7, 16, 19, 15, tzinfo=BEIJING_TZ)
    source = write_synthetic_etext(
        tmp_path / "dqyc.dat",
        contract,
        start=start,
        steps=contract.model_steps,
    )

    with pytest.raises(NwpETextValidationError, match="生产命名契约"):
        validate_etext(read_etext(source), contract)
