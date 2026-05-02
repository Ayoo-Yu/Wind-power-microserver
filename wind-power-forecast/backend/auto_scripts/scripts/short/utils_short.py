"""Short-term pipeline utilities.

Thin wrapper that re-exports everything from :pymod:`utils_base`.
"""
import os
import sys

# Ensure parent directory is importable
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_current_dir, '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from utils_base import (  # noqa: F401
    set_today,
    get_current_farm_code,
    get_farm_capacity,
    get_evaluation_capacity,
    normalize_rmse_score,
    visualize_results,
    calculate_rmse,
    calculate_k,
    calculate_daily_averaged_k,
    evaluate_with_time_weights,
)

from config_short import Today  # noqa: F401  (backward compat)

# Inject Today into utils_base so visualize_results can use it
set_today(Today)
