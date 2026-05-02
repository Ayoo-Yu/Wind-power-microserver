"""Middle-term pipeline model parameters.

Thin wrapper that re-exports everything from :pymod:`models_base`.
"""
import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_current_dir, '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from models_base import (  # noqa: F401
    PARAM_VERSIONS,
    get_latest_param_version,
    get_lightgbm_params,
    get_unified_params,
    get_quantile_params,
    add_new_param_version,
    save_param_versions_to_file,
)
