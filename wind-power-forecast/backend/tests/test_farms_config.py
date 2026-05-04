import pytest


def test_get_all_farms_returns_5_farms():
    from farm_registry.farms_config import get_all_farms
    farms = get_all_farms()
    assert len(farms) == 5


def test_get_farm_by_code():
    from farm_registry.farms_config import get_farm
    farm = get_farm("dplz")
    assert farm["farm_code"] == "dplz"
    assert farm["capacity_mw"] == 47.5
    assert farm["calibrate_enabled"] is True
    assert farm["short_table"] == "train_pre_short_dplz"
    assert farm["mid_table"] == "train_pre_middle_dplz"


def test_get_farm_zyx_no_calibration():
    from farm_registry.farms_config import get_farm
    farm = get_farm("zyx")
    assert farm["calibrate_enabled"] is False
    assert farm["capacity_mw"] == 453.5


def test_get_farm_unknown_raises():
    from farm_registry.farms_config import get_farm
    with pytest.raises(KeyError):
        get_farm("unknown")


def test_farm_codes_list():
    from farm_registry.farms_config import get_farm_codes
    codes = get_farm_codes()
    assert set(codes) == {"dplz", "sds", "zyx", "cf", "bnj"}
