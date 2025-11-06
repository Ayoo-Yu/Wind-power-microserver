"""对外暴露训练/预测流程封装。"""

from .train import run_training, TrainingResult  # noqa: F401
from .predict import run_prediction, PredictionResult  # noqa: F401

__all__ = [
    "run_training",
    "TrainingResult",
    "run_prediction",
    "PredictionResult",
]


