#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟数据接收端服务器
用于测试风电功率数据上报功能
"""

from flask import Flask, request, jsonify
import json
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mock_receiver.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

# 存储接收到的数据
received_data = []

@app.route('/receive-data', methods=['POST'])
def receive_data():
    """接收风电功率数据"""
    try:
        # 获取请求数据
        data = request.get_json()
        
        # 记录接收时间
        receive_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 添加接收时间到数据中
        data_with_time = {
            'receive_time': receive_time,
            'data': data
        }
        
        # 存储数据
        received_data.append(data_with_time)
        
        # 打印接收到的数据（用于调试）
        logging.info(f"=== 接收到数据 ===")
        logging.info(f"接收时间: {receive_time}")
        logging.info(f"数据类型: {data.get('report_type', '未知')}")
        logging.info(f"数据量: {len(data.get('data', []))}")
        logging.info(f"完整数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # 返回成功响应
        response = {
            'status': 'success',
            'message': '数据接收成功',
            'received_count': len(data.get('data', [])),
            'timestamp': receive_time
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logging.error(f"接收数据时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'接收数据失败: {str(e)}'
        }), 500

@app.route('/status', methods=['GET'])
def get_status():
    """获取接收端状态"""
    return jsonify({
        'status': 'running',
        'total_received': len(received_data),
        'last_receive_time': received_data[-1]['receive_time'] if received_data else None,
        'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/history', methods=['GET'])
def get_history():
    """获取接收历史"""
    # 获取最近的10条记录
    recent_data = received_data[-10:] if len(received_data) > 10 else received_data
    
    return jsonify({
        'total_count': len(received_data),
        'recent_data': recent_data
    })

@app.route('/clear', methods=['POST'])
def clear_data():
    """清空接收的数据"""
    global received_data
    count = len(received_data)
    received_data = []
    
    logging.info(f"清空了 {count} 条接收记录")
    
    return jsonify({
        'status': 'success',
        'message': f'已清空 {count} 条记录'
    })

@app.route('/', methods=['GET'])
def index():
    """首页，显示服务器信息"""
    return jsonify({
        'service': '风电功率数据接收端模拟器',
        'version': '1.0.0',
        'endpoints': {
            'POST /receive-data': '接收风电功率数据',
            'GET /status': '获取服务器状态',
            'GET /history': '获取接收历史',
            'POST /clear': '清空接收数据'
        },
        'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_received': len(received_data)
    })

if __name__ == '__main__':
    print("=" * 50)
    print("风电功率数据接收端模拟器")
    print("=" * 50)
    print("服务地址: http://localhost:8081")
    print("接收接口: POST http://localhost:8081/receive-data")
    print("状态查询: GET http://localhost:8081/status")
    print("接收历史: GET http://localhost:8081/history")
    print("清空数据: POST http://localhost:8081/clear")
    print("=" * 50)
    
    # 启动服务器
    app.run(host='0.0.0.0', port=8081, debug=True) 