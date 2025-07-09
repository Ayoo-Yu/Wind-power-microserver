from datetime import datetime
from config import MINIO_CONFIG

def get_model_path(model_type, model_name):
    return f"{model_type}/models/{datetime.now().strftime('%Y%m%d')}/{model_name}.joblib"

def get_scaler_path(model_type):
    return f"{model_type}/scalers/{datetime.now().strftime('%Y%m%d%H%M')}_scaler.joblib"

def get_prediction_path(prediction_type, model_id):
    return f"{prediction_type}/predictions/{model_id}/{datetime.now().strftime('%Y%m%d%H%M')}.csv"

def get_metrics_path(model_id):
    return f"metrics/{model_id}/{datetime.now().strftime('%Y%m%d%H%M')}_metrics.json" 