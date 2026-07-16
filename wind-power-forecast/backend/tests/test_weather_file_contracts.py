import re

import pytest

from routes.weather_fetch_router import _validate_task_path_pattern
from services.ssh_service import SSHService


def test_weather_filename_template_matches_timestamp_tokens_and_wildcards():
    service = SSHService()
    pattern = service._convert_file_pattern_to_regex('NWP_${YYYYMMDDHH}_*.csv')

    assert re.match(pattern, 'NWP_2026071608_DQ.csv')
    assert not re.match(pattern, 'NWP_20260716_DQ.csv')
    assert not re.match(pattern, 'NWP_2026071608_DQ.txt')


def test_weather_flat_directory_pattern_uses_base_path(monkeypatch):
    service = SSHService()

    class _Sftp:
        def stat(self, path):
            assert path == '/ECMWF/yunnan_test'

        def listdir_attr(self, path):
            assert path == '/ECMWF/yunnan_test'
            return []

        def close(self):
            return None

    class _Client:
        def open_sftp(self):
            return _Sftp()

    monkeypatch.setattr(service, 'create_connection', lambda config: 'connection-1')
    monkeypatch.setattr(service, 'close_connection', lambda connection_id: None)
    service.connections['connection-1'] = _Client()

    files = service.list_files_dynamic_path(
        {},
        '/ECMWF/yunnan_test',
        'flat',
        'latest',
        file_pattern='*.grib2',
    )

    assert files == []


def test_weather_custom_directory_requires_an_effective_template():
    with pytest.raises(ValueError, match='自定义时间目录格式不能为空'):
        _validate_task_path_pattern({
            'path_pattern': 'custom',
            'custom_path_pattern': '',
        })

    with pytest.raises(ValueError, match='自定义时间目录格式不能为空'):
        _validate_task_path_pattern(
            {'custom_path_pattern': ''},
            default_path_pattern='custom',
            default_custom_path_pattern='YYYY/MM/DD/HH',
        )

    _validate_task_path_pattern({
        'path_pattern': 'custom',
        'custom_path_pattern': 'YYYY/MM/DD/HH',
    })
