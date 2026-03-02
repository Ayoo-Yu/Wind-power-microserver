from flask import Blueprint

from routes.farm_management import get_farms

v1_compat_bp = Blueprint("v1_compat", __name__, url_prefix="/api/v1")


@v1_compat_bp.route("/farms", methods=["GET"])
def get_farms_v1():
    """
    v1 compat bridge:
    - `/api/v1/farms` reuses current `/api/farms` handler behavior.
    - `/api/auth/*` stays on legacy paths for now (pending migration).
    """
    return get_farms()

