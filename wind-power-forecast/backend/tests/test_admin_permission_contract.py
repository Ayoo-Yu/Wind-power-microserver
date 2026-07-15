from types import SimpleNamespace

from routes.auth import is_admin_role


def test_system_administrator_role_has_backend_admin_semantics():
    role = SimpleNamespace(name="系统管理员")

    assert is_admin_role(role) is True
