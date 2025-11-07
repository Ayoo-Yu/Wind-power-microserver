// src/services/apiService.js
import axiosInstance from '../api/axios';
import { getSelectedWindFarmCode } from '../store/windFarm';

// 确定API基础URL
let backendBaseUrl = process.env.VUE_APP_BASE_API;

if (!backendBaseUrl) {
  if (window.location.hostname !== 'localhost') {
    backendBaseUrl = `${window.location.origin}/api`;
  } else {
    backendBaseUrl = '/api';
  }
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

  formData.append('wind_farm_code', getSelectedWindFarmCode());

  return axiosInstance.post('upload_train_csv', formData, {
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

  formData.append('wind_farm_code', getSelectedWindFarmCode());

  return axiosInstance.post('upload_predict_csv', formData, {
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

  formData.append('wind_farm_code', getSelectedWindFarmCode());

  return axiosInstance.post('upload_model', formData, {
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

  formData.append('wind_farm_code', getSelectedWindFarmCode());

  return axiosInstance.post('upload_scaler', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const modeltrain = (fileId, model, wfcapacity, trainRatio, customParams = null) => {
  const requestData = { file_id: fileId, model, wfcapacity, train_ratio: trainRatio, wind_farm_code: getSelectedWindFarmCode() };
  
  // 如果是自定义模型，添加自定义参数
  if (model === 'CUSTOM' && customParams) {
    requestData.custom_params = customParams;
  }
  
  return axiosInstance.post('modeltrain', requestData, {
    timeout: 1800000  // 设置3分钟超时，适当增加以适应大模型的初始化时间
  });
};

export const checkTrainingStatus = (fileId) => {
  return axiosInstance.get('check-training-status', {
    params: { file_id: fileId, wind_farm_code: getSelectedWindFarmCode() }
  });
};

export const predict = (csvfileId, modelfileId, scalerfileId) => {
  return axiosInstance.post('predict', {
    csvfileId: csvfileId,
    modelfileId: modelfileId,
    scalerfileId: scalerfileId,
    wind_farm_code: getSelectedWindFarmCode(),
  });
};

export const getActualValues = async (startTime, endTime) => {
  try {
    const response = await axiosInstance.post('power-compare/data', {
      start: startTime,
      end: endTime,
      types: ['实测值']
    }, {
      headers: {
        'X-Windfarm-Code': getSelectedWindFarmCode(),
      }
    });
    return response;
  } catch (error) {
    console.error('获取实测值失败:', error);
    throw error;
  }
};

