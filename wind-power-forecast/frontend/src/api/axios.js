import axios from 'axios';
import { ElMessage } from 'element-plus';
import router from '../router';
import { isAuthReady, isAuthLoading } from '../store/authReady'; // 导入认证状态

// 确定API基础URL
let API_BASE_URL;

// 如果不是localhost，使用当前域名+端口
if (window.location.hostname !== 'localhost') {
  API_BASE_URL = `http://${window.location.hostname}:8080`; // 通过Nginx反向代理
} else {
  API_BASE_URL = 'http://localhost:8080'; // 本地开发环境也通过Nginx
}

console.log('使用API基础URL:', API_BASE_URL);

// 创建axios实例
const instance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: false,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 请求拦截器
instance.interceptors.request.use(
  config => {
    console.log('发送请求:', config.method.toUpperCase(), config.url);
    
    // 从localStorage获取访问令牌
    const token = localStorage.getItem('accessToken');
    
    // 如果有token，添加到Authorization请求头
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
      console.log('已添加认证令牌到请求:', config.url);
    } else {
      console.warn('请求未携带认证令牌:', config.url);
    }
    
    return config;
  },
  error => {
    console.error('请求错误:', error);
    return Promise.reject(error);
  }
);

// 响应拦截器
instance.interceptors.response.use(
  response => {
    console.log('收到响应:', response.status, response.config.url);
    return response;
  },
  error => {
    // 详细日志错误信息
    console.error('响应错误:', error.message);
    if (error.response) {
      console.error('状态码:', error.response.status);
      console.error('响应数据:', error.response.data);
      console.error('请求URL:', error.config?.url);
      
      // 处理401未授权错误 - token无效或过期
      if (error.response.status === 401) {
        console.warn('认证失败或令牌过期，需要重新登录 (URL:', error.config?.url, ')');
        
        // 清除本地存储的认证信息
        localStorage.removeItem('accessToken');
        localStorage.removeItem('user');
        
        // 更新认证状态
        isAuthReady.value = false;
        isAuthLoading.value = false;
        
        // 显示消息提示用户
        ElMessage.error('您的登录已过期，请重新登录');
        
        // 如果当前不在登录页，重定向到登录页
        if (router.currentRoute.value.path !== '/login') {
          router.push('/login');
        }
      }
    } else if (error.request) {
      console.error('请求已发送但未收到响应');
      console.error('请求详情:', error.request);
    }
    
    // 处理错误情况
    if (error.message === 'Network Error') {
      ElMessage.error('网络错误，请检查您的网络连接或服务器状态');
    } else if (!error.response || error.response.status !== 401) {
      // 只显示非401错误的消息（因为401已在上面处理）
      ElMessage.error(error.response?.data?.message || '请求失败');
    }
    
    return Promise.reject(error);
  }
);

export default instance; 