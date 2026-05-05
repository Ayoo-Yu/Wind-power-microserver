"""Test upload a small CSV to train_pre_short_bnj via the API."""
import requests

url = "http://localhost:5000/api/upload_feature_csv"
csv_path = r"D:\weather_data\csv_short\bainijing\2026-05_short.csv"

with open(csv_path, "rb") as f:
    files = {"file": ("test.csv", f, "text/csv")}
    data = {"table_name": "train_pre_short_bnj", "farm_code": "BNJ"}
    resp = requests.post(url, files=files, data=data, timeout=600)

print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
