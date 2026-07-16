import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager, create_access_token

from routes.actual_power_router import actual_power_bp
from routes.autopredict import autopredict_bp
from routes.etext_pipeline_router import etext_pipeline_bp
from routes.extreme_weather_router import extreme_weather_bp
from routes.feature_upload import feature_upload_bp
from routes.operational_data_upload import operational_data_upload_bp
from routes.power_compare import bp as power_compare_bp
from routes.prediction2database import prediction2database_bp
from routes.report_management_router import report_management_bp
from routes.user import user_bp
from routes.v1_compat import v1_compat_bp
from services import auth_service
from utils import authorization
from utils.authorization import permission_required


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.value


class _Session:
    def __init__(self, value):
        self.value = value

    def query(self, model):
        return _Query(self.value)


def _app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        JWT_SECRET_KEY="route-authorization-test-secret-value",
    )
    JWTManager(app)
    return app


def _user(*, role_name="运行操作人员", permissions=None, active=True):
    role = SimpleNamespace(
        name=role_name,
        permissions={"permissions": list(permissions or [])},
    )
    return SimpleNamespace(
        id="1",
        username="operator",
        is_active=active,
        role=role,
    )


def _patch_user(monkeypatch, user):
    @contextmanager
    def fake_db_session():
        yield _Session(user)

    monkeypatch.setattr(authorization, "db_session", fake_db_session)


def _token(app):
    with app.app_context():
        return create_access_token(identity="1")


def test_permission_decorator_rejects_forged_username_without_jwt(monkeypatch):
    app = _app()
    entered_database = False

    @contextmanager
    def forbidden_db_session():
        nonlocal entered_database
        entered_database = True
        yield _Session(None)

    monkeypatch.setattr(authorization, "db_session", forbidden_db_session)

    @app.get("/protected")
    @permission_required("manage_roles")
    def protected():
        return jsonify({"ok": True})

    response = app.test_client().get("/protected?username=admin")

    assert response.status_code == 401
    assert entered_database is False


def test_permission_decorator_enforces_database_role(monkeypatch):
    app = _app()

    @app.get("/protected")
    @permission_required("manage_reports")
    def protected():
        return jsonify({"ok": True})

    token = _token(app)
    _patch_user(monkeypatch, _user(permissions=["view_all_data"]))
    denied = app.test_client().get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    _patch_user(monkeypatch, _user(permissions=["manage_reports"]))
    allowed = app.test_client().get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_admin_role_and_active_state_are_enforced(monkeypatch):
    app = _app()

    @app.get("/protected")
    @permission_required("configure_system")
    def protected():
        return jsonify({"ok": True})

    token = _token(app)
    _patch_user(monkeypatch, _user(role_name="系统管理员"))
    admin_response = app.test_client().get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    _patch_user(monkeypatch, _user(role_name="系统管理员", active=False))
    inactive_response = app.test_client().get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert admin_response.status_code == 200
    assert inactive_response.status_code == 403


def test_legacy_jwt_helper_has_no_built_in_secret(monkeypatch):
    for name in ("JWT_SECRET", "JWT_SECRET_KEY", "SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError):
        auth_service._get_jwt_secret()

    monkeypatch.setenv("SECRET_KEY", "field-jwt-secret-value")
    assert auth_service._get_jwt_secret() == "field-jwt-secret-value"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/user/users"),
        ("post", "/actual_power/"),
        ("post", "/prediction2database/batch_shortl_power"),
        ("get", "/report/configs"),
        ("post", "/power/data"),
        ("put", "/api/etext_pipeline/config"),
        ("put", "/extreme/thresholds"),
        ("post", "/api/upload_feature_csv"),
        ("post", "/operational/api/upload_operational_csv"),
        ("get", "/autopredict/status"),
        ("get", "/api/v1/report/configs"),
    ],
)
def test_sensitive_blueprints_reject_anonymous_requests(method, path):
    app = _app()
    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(actual_power_bp)
    app.register_blueprint(prediction2database_bp)
    app.register_blueprint(report_management_bp, url_prefix="/report")
    app.register_blueprint(power_compare_bp, url_prefix="/power")
    app.register_blueprint(etext_pipeline_bp)
    app.register_blueprint(extreme_weather_bp, url_prefix="/extreme")
    app.register_blueprint(feature_upload_bp)
    app.register_blueprint(operational_data_upload_bp, url_prefix="/operational")
    app.register_blueprint(autopredict_bp, url_prefix="/autopredict")
    app.register_blueprint(v1_compat_bp)

    response = getattr(app.test_client(), method)(path)

    assert response.status_code == 401


def test_all_mutation_routes_declare_an_authentication_boundary():
    """新增写接口必须显式授权，或位于带 before_request 的受控蓝图。"""

    routes_dir = Path(__file__).resolve().parents[1] / "routes"
    internal_allowlist = {
        ("auth.py", "login"),
        ("scada_connection.py", "worker_status"),
        ("scada_connection.py", "ingest_sample"),
    }
    unprotected = []

    for path in sorted(routes_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        protected_blueprints = set()
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                decorator_text = ast.unparse(decorator)
                if decorator_text.endswith(".before_request"):
                    protected_blueprints.add(decorator_text.split(".", 1)[0])

        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route_decorators = []
            auth_decorators = []
            for decorator in node.decorator_list:
                decorator_text = ast.unparse(decorator)
                if ".route(" in decorator_text:
                    route_decorators.append(decorator_text)
                if any(
                    marker in decorator_text
                    for marker in (
                        "jwt_required",
                        "permission_required",
                        "token_required",
                        "_management_required",
                    )
                ):
                    auth_decorators.append(decorator_text)
            if not route_decorators:
                continue
            route_text = " ".join(route_decorators)
            if not any(
                f"'{method}'" in route_text or f'"{method}"' in route_text
                for method in ("POST", "PUT", "PATCH", "DELETE")
            ):
                continue
            blueprint = route_decorators[0].split(".", 1)[0]
            if auth_decorators or blueprint in protected_blueprints:
                continue
            key = (path.name, node.name)
            if key not in internal_allowlist:
                unprotected.append(f"{path.name}:{node.lineno}:{node.name}")

    assert unprotected == []
