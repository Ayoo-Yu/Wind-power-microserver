# API 使用示例（中文）

## 1. 登录获取令牌
```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

## 2. 健康检查
```bash
curl http://localhost:5000/health
curl http://localhost:5000/api/v1/health
```

## 3. 上传训练数据
```bash
curl -X POST http://localhost:5000/upload_train_csv \
  -H "Authorization: Bearer <令牌>" \
  -F "file=@train.csv" \
  -F "data_type=traincsv" \
  -F "description=训练样本"
```

## 4. 上传预测数据
```bash
curl -X POST http://localhost:5000/upload_predict_csv \
  -H "Authorization: Bearer <令牌>" \
  -F "file=@predict.csv" \
  -F "data_type=predictcsv"
```

## 5. 上传模型文件
```bash
curl -X POST http://localhost:5000/upload_model \
  -H "Authorization: Bearer <令牌>" \
  -F "file=@model.pkl" \
  -F "data_type=model"
```

## 6. 错误处理建议
- 状态码 `400`：请求参数错误。
- 状态码 `401`：认证失败或令牌失效。
- 状态码 `500`：服务内部错误，查看后端日志。

## 7. Python 调用示例
```python
import requests

base_url = "http://localhost:5000"
resp = requests.get(f"{base_url}/health", timeout=10)
print(resp.status_code, resp.json())
```

## 8. 调用规范
- 所有时间参数建议使用 ISO8601。
- 上传接口统一使用 `multipart/form-data`。
- 生产环境必须走 HTTPS。
