import time
import json
from datetime import datetime, timedelta
from locust import HttpUser, task, between

class BackendUser(HttpUser):
    # wait_time = between(1, 3)  # 模拟用户在每个任务执行后等待1-3秒
    host = "http://localhost:8080"  # 重要：这里是Nginx暴露的地址和端口，根据实际情况修改

    _user_credentials = {"username": "admin", "password": "admin123"}  # 替换为有效的测试用户名和密码
    _access_token = None

    def on_start(self):
        """在测试开始时，每个模拟用户执行一次，用于登录获取token"""
        print("用户开始测试 - 正在登录")
        response = None  # 初始化response变量
        try:
            # 注意：加上/api前缀，以便nginx正确转发
            response = self.client.post("/api/auth/login", json=self._user_credentials, name="/api/auth/login")
            response.raise_for_status()
            json_response = response.json()
            if "access_token" in json_response:
                self._access_token = json_response["access_token"]
                print(f"登录成功，已获取token (用户: {self._user_credentials['username']})")
            else:
                print(f"登录失败：响应中没有'access_token'。状态码: {response.status_code}, 响应: {response.text}")
                # 可以在这里让用户停止
                if self.environment and self.environment.runner:
                    self.environment.runner.quit()
        except Exception as e:
            status_code = response.status_code if response is not None else "N/A"
            response_text = response.text if response is not None else "N/A"
            print(f"登录请求异常：{e}. 状态码: {status_code}, 响应: {response_text}")
            # 停止测试以避免后续无效请求
            if self.environment and self.environment.runner:
                self.environment.runner.quit()
            else:
                print("Runner不可用，无法停止测试。")

    @task(10)  # 数字代表任务权重，数字越大，执行频率越高
    def get_users(self):
        """测试获取用户列表的API"""
        if self._access_token:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            try:
                response = self.client.get("/api/auth/users", headers=headers, name="/api/auth/users")
                response.raise_for_status()
            except Exception as e:
                print(f"获取用户列表失败：{e} - 状态码：{response.status_code if 'response' in locals() else 'N/A'}")
                if 'response' in locals():
                    print(f"响应内容: {response.text}")
        else:
            time.sleep(1)  # 如果没有token，稍微等一下避免空转

    @task(5)
    def get_roles(self):
        """测试获取角色列表的API"""
        if self._access_token:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            try:
                response = self.client.get("/api/auth/roles", headers=headers, name="/api/auth/roles")
                response.raise_for_status()
            except Exception as e:
                print(f"获取角色列表失败：{e} - 状态码：{response.status_code if 'response' in locals() else 'N/A'}")
                if 'response' in locals():
                    print(f"响应内容: {response.text}")
        else:
            time.sleep(1)
            
    @task(8)
    def get_power_compare_data(self):
        """测试获取功率比较数据API"""
        if self._access_token:
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json"
            }
            
            # 创建一个时间范围查询
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # 查询最近7天的数据
            
            data = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "types": ["实测值", "超短期预测", "短期预测"]
            }
            
            try:
                response = self.client.post(
                    "/api/power-compare/data", 
                    json=data,
                    headers=headers, 
                    name="/api/power-compare/data"
                )
                response.raise_for_status()
            except Exception as e:
                print(f"获取功率比较数据失败：{e} - 状态码：{response.status_code if 'response' in locals() else 'N/A'}")
                if 'response' in locals():
                    print(f"响应内容: {response.text}")
        else:
            time.sleep(1)
            
    @task(2)
    def get_user_info(self):
        """测试获取当前用户信息的API"""
        if self._access_token:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            try:
                response = self.client.get(
                    "/api/auth/me", 
                    headers=headers,
                    name="/api/auth/me"
                )
                response.raise_for_status()
            except Exception as e:
                print(f"获取用户信息失败：{e} - 状态码：{response.status_code if 'response' in locals() else 'N/A'}")
                if 'response' in locals():
                    print(f"响应内容: {response.text}")
        else:
            time.sleep(1)
            
    @task(4)
    def get_autopredict_status(self):
        """测试自动预测API (连接到autopredict后端)"""
        if self._access_token:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            try:
                # 这个API路径会匹配nginx中的正则表达式规则
                response = self.client.get(
                    "/api/status", 
                    headers=headers,
                    name="/api/status"
                )
                response.raise_for_status()
            except Exception as e:
                print(f"获取自动预测状态失败：{e} - 状态码：{response.status_code if 'response' in locals() else 'N/A'}")
                if 'response' in locals():
                    print(f"响应内容: {response.text}")
        else:
            time.sleep(1)

    # 如果需要测试写入密集型API，可以取消下面的注释并适当修改
    # @task(2)
    # def create_some_resource(self):
    #     """测试创建资源的API（写入密集型）"""
    #     if self._access_token:
    #         headers = {"Authorization": f"Bearer {self._access_token}"}
    #         data = {"name": "test resource", "description": "created by load test"}
    #         try:
    #             response = self.client.post("/api/resource", json=data, headers=headers, name="/api/resource")
    #             response.raise_for_status()
    #         except Exception as e:
    #             print(f"创建资源失败：{e} - 状态码：{response.status_code if 'response' in locals() else 'N/A'}")
    #     else:
    #         time.sleep(1)