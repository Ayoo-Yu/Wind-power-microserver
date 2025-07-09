// src/services/apiService.js
import axios from 'axios';

// 确定API基础URL
let backendBaseUrl;

// 如果不是localhost，使用当前域名+端口
if (window.location.hostname !== 'localhost') {
  backendBaseUrl = `http://${window.location.hostname}:5000`; // 明确指定后端端口为5000
} else {
  backendBaseUrl = 'http://localhost:5000'; // 本地开发环境
}

console.log('apiService使用API基础URL:', backendBaseUrl);

export const upload_train_csv = (file, onUploadProgress) => {
  // 检查文件类型是否是 joblib
  const allowedExtensions = ['csv']; // 可支持的文件类型扩展名
  const fileExtension = file.name.split('.').pop().toLowerCase();

  if (!allowedExtensions.includes(fileExtension)) {
    return Promise.reject(new Error(`Unsupported file type: ${fileExtension}. Allowed types are: ${allowedExtensions.join(', ')}`));
  }

  const formData = new FormData();
  formData.append('file', file);

  return axios.post(`${backendBaseUrl}/upload_train_csv`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const upload_predict_csv = (file, onUploadProgress) => {
  // 检查文件类型是否是 joblib
  const allowedExtensions = ['csv']; // 可支持的文件类型扩展名
  const fileExtension = file.name.split('.').pop().toLowerCase();

  if (!allowedExtensions.includes(fileExtension)) {
    return Promise.reject(new Error(`Unsupported file type: ${fileExtension}. Allowed types are: ${allowedExtensions.join(', ')}`));
  }

  const formData = new FormData();
  formData.append('file', file);

  return axios.post(`${backendBaseUrl}/upload_predict_csv`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const upload_model = (file, onUploadProgress) => {
  // 检查文件类型是否是 joblib
  const allowedExtensions = ['joblib']; // 可支持的文件类型扩展名
  const fileExtension = file.name.split('.').pop().toLowerCase();

  if (!allowedExtensions.includes(fileExtension)) {
    return Promise.reject(new Error(`Unsupported file type: ${fileExtension}. Allowed types are: ${allowedExtensions.join(', ')}`));
  }

  const formData = new FormData();
  formData.append('file', file);

  return axios.post(`${backendBaseUrl}/upload_model`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const upload_scaler = (file, onUploadProgress) => {
  // 检查文件类型是否是 joblib
  const allowedExtensions = ['joblib']; // 可支持的文件类型扩展名
  const fileExtension = file.name.split('.').pop().toLowerCase();

  if (!allowedExtensions.includes(fileExtension)) {
    return Promise.reject(new Error(`Unsupported file type: ${fileExtension}. Allowed types are: ${allowedExtensions.join(', ')}`));
  }

  const formData = new FormData();
  formData.append('file', file);

  return axios.post(`${backendBaseUrl}/upload_scaler`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const modeltrain = (fileId, model, wfcapacity, trainRatio, customParams = null) => {
  const requestData = { file_id: fileId, model, wfcapacity, train_ratio: trainRatio };
  
  // 如果是自定义模型，添加自定义参数
  if (model === 'CUSTOM' && customParams) {
    requestData.custom_params = customParams;
  }
  
  return axios.post(`${backendBaseUrl}/modeltrain`, requestData, {
    timeout: 1800000  // 设置3分钟超时，适当增加以适应大模型的初始化时间
  });
};

export const checkTrainingStatus = (fileId) => {
  return axios.get(`${backendBaseUrl}/check-training-status`, {
    params: { file_id: fileId }
  });
};

export const predict = (csvfileId, modelfileId, scalerfileId) => {
  return axios.post(`${backendBaseUrl}/predict`, { csvfileId: csvfileId, modelfileId:modelfileId, scalerfileId:scalerfileId});
};

export const getActualValues = async (startTime, endTime) => {
  try {
    const response = await axios.post(`${backendBaseUrl}/power-compare/data`, {
      start: startTime,
      end: endTime,
      types: ['实测值']
    });
    return response;
  } catch (error) {
    console.error('获取实测值失败:', error);
    throw error;
  }
};

