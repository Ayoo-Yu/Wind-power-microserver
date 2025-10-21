// src/services/apiServiceEnhanced.js
import axios from 'axios';
import farmService from '../utils/farmService';

// 确定API基础URL
let backendBaseUrl;

// 如果不是localhost，使用当前域名+端口
if (window.location.hostname !== 'localhost') {
  backendBaseUrl = `http://${window.location.hostname}:5000`; // 明确指定后端端口为5000
} else {
  backendBaseUrl = 'http://localhost:5000'; // 本地开发环境
}

console.log('增强版API服务使用API基础URL:', backendBaseUrl);

/**
 * 创建带有场站参数的请求数据
 * @param {Object} data - 原始请求数据
 * @returns {Object} - 包含场站参数的请求数据
 */
const createFarmAwareData = (data = {}) => {
  return {
    ...data,
    farm_code: farmService.getCurrentFarm()
  };
};

/**
 * 创建带有场站参数的请求配置
 * @param {Object} config - 原始请求配置
 * @returns {Object} - 包含场站参数的请求配置
 */
const createFarmAwareConfig = (config = {}) => {
  const farmAwareConfig = { ...config };

  // 确保params存在
  if (!farmAwareConfig.params) {
    farmAwareConfig.params = {};
  }

  // 添加场站参数
  farmAwareConfig.params.farm_code = farmService.getCurrentFarm();

  return farmAwareConfig;
};

// 文件上传相关API（带场站参数）
export const upload_train_csv = (file, onUploadProgress, farmCode = null) => {
  const allowedExtensions = ['csv'];
  const fileExtension = file.name.split('.').pop().toLowerCase();

  if (!allowedExtensions.includes(fileExtension)) {
    return Promise.reject(new Error(`不支持的文件类型: ${fileExtension}. 允许的类型: ${allowedExtensions.join(', ')}`));
  }

  const formData = new FormData();
  formData.append('file', file);

  // 添加场站参数
  const targetFarmCode = farmCode || farmService.getCurrentFarm();
  formData.append('farm_code', targetFarmCode);

  return axios.post(`${backendBaseUrl}/upload_train_csv`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const upload_predict_csv = (file, onUploadProgress, farmCode = null) => {
  const allowedExtensions = ['csv'];
  const fileExtension = file.name.split('.').pop().toLowerCase();

  if (!allowedExtensions.includes(fileExtension)) {
    return Promise.reject(new Error(`不支持的文件类型: ${fileExtension}. 允许的类型: ${allowedExtensions.join(', ')}`));
  }

  const formData = new FormData();
  formData.append('file', file);

  // 添加场站参数
  const targetFarmCode = farmCode || farmService.getCurrentFarm();
  formData.append('farm_code', targetFarmCode);

  return axios.post(`${backendBaseUrl}/upload_predict_csv`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const upload_model = (file, onUploadProgress, farmCode = null) => {
  const allowedExtensions = ['joblib'];
  const fileExtension = file.name.split('.').pop().toLowerCase();

  if (!allowedExtensions.includes(fileExtension)) {
    return Promise.reject(new Error(`不支持的文件类型: ${fileExtension}. 允许的类型: ${allowedExtensions.join(', ')}`));
  }

  const formData = new FormData();
  formData.append('file', file);

  // 添加场站参数
  const targetFarmCode = farmCode || farmService.getCurrentFarm();
  formData.append('farm_code', targetFarmCode);

  return axios.post(`${backendBaseUrl}/upload_model`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const upload_scaler = (file, onUploadProgress, farmCode = null) => {
  const allowedExtensions = ['joblib'];
  const fileExtension = file.name.split('.').pop().toLowerCase();

  if (!allowedExtensions.includes(fileExtension)) {
    return Promise.reject(new Error(`不支持的文件类型: ${fileExtension}. 允许的类型: ${allowedExtensions.join(', ')}`));
  }

  const formData = new FormData();
  formData.append('file', file);

  // 添加场站参数
  const targetFarmCode = farmCode || farmService.getCurrentFarm();
  formData.append('farm_code', targetFarmCode);

  return axios.post(`${backendBaseUrl}/upload_scaler`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

// 模型训练相关API
export const modeltrain = (fileId, model, wfcapacity, trainRatio, customParams = null) => {
  const requestData = createFarmAwareData({
    file_id: fileId,
    model,
    wfcapacity,
    train_ratio: trainRatio
  });

  // 如果是自定义模型，添加自定义参数
  if (model === 'CUSTOM' && customParams) {
    requestData.custom_params = customParams;
  }

  return axios.post(`${backendBaseUrl}/modeltrain`, requestData, {
    timeout: 1800000  // 设置3分钟超时
  });
};

export const checkTrainingStatus = (fileId) => {
  return axios.get(`${backendBaseUrl}/check-training-status`, {
    params: createFarmAwareConfig({ file_id: fileId }).params
  });
};

// 预测相关API
export const predict = (csvfileId, modelfileId, scalerfileId) => {
  const requestData = createFarmAwareData({
    csvfileId: csvfileId,
    modelfileId: modelfileId,
    scalerfileId: scalerfileId
  });

  return axios.post(`${backendBaseUrl}/predict`, requestData);
};

export const getActualValues = async (startTime, endTime) => {
  try {
    const requestData = createFarmAwareData({
      start: startTime,
      end: endTime,
      types: ['实测值']
    });

    const response = await axios.post(`${backendBaseUrl}/power-compare/data`, requestData);
    return response;
  } catch (error) {
    console.error('获取实测值失败:', error);
    throw error;
  }
};

// 数据对比相关API
export const getPowerCompareData = async (startTime, endTime, types = ['实测值', '预测值', '理论功率']) => {
  try {
    const requestData = createFarmAwareData({
      start: startTime,
      end: endTime,
      types: types
    });

    const response = await axios.post(`${backendBaseUrl}/power-compare/data`, requestData);
    return response;
  } catch (error) {
    console.error('获取功率对比数据失败:', error);
    throw error;
  }
};

// 数据集管理API
export const getDatasets = async (params = {}) => {
  try {
    const config = createFarmAwareConfig(params);
    const response = await axios.get(`${backendBaseUrl}/api/datasets`, config);
    return response;
  } catch (error) {
    console.error('获取数据集列表失败:', error);
    throw error;
  }
};

export const getDatasetById = async (datasetId) => {
  try {
    const config = createFarmAwareConfig();
    const response = await axios.get(`${backendBaseUrl}/api/datasets/${datasetId}`, config);
    return response;
  } catch (error) {
    console.error('获取数据集详情失败:', error);
    throw error;
  }
};

// 预测结果管理API
export const getPredictions = async (params = {}) => {
  try {
    const config = createFarmAwareConfig(params);
    const response = await axios.get(`${backendBaseUrl}/api/predictions`, config);
    return response;
  } catch (error) {
    console.error('获取预测结果失败:', error);
    throw error;
  }
};

export const getPredictionById = async (predictionId) => {
  try {
    const config = createFarmAwareConfig();
    const response = await axios.get(`${backendBaseUrl}/api/predictions/${predictionId}`, config);
    return response;
  } catch (error) {
    console.error('获取预测结果详情失败:', error);
    throw error;
  }
};

// 系统状态API
export const getSystemStatus = async () => {
  try {
    const config = createFarmAwareConfig();
    const response = await axios.get(`${backendBaseUrl}/system/status`, config);
    return response;
  } catch (error) {
    console.error('获取系统状态失败:', error);
    throw error;
  }
};

// 场站管理API
export const getFarmList = async () => {
  try {
    const response = await axios.get(`${backendBaseUrl}/api/farms`);
    return response;
  } catch (error) {
    console.error('获取场站列表失败:', error);
    throw error;
  }
};

export const getFarmInfo = async (farmCode) => {
  try {
    const response = await axios.get(`${backendBaseUrl}/api/farms/${farmCode}`);
    return response;
  } catch (error) {
    console.error('获取场站信息失败:', error);
    throw error;
  }
};

// 统计分析API
export const getFarmStatistics = async (farmCode, params = {}) => {
  try {
    const config = createFarmAwareConfig(params);
    const response = await axios.get(`${backendBaseUrl}/api/farms/${farmCode}/statistics`, config);
    return response;
  } catch (error) {
    console.error('获取场站统计失败:', error);
    throw error;
  }
};

export const getPredictionStatistics = async (params = {}) => {
  try {
    const config = createFarmAwareConfig(params);
    const response = await axios.get(`${backendBaseUrl}/api/statistics/predictions`, config);
    return response;
  } catch (error) {
    console.error('获取预测统计失败:', error);
    throw error;
  }
};

/**
 * 检查数据是否属于当前场站
 * @param {Array|Object} data - 数据或数据数组
 * @returns {Array|Object} - 过滤后的数据
 */
export const filterCurrentFarmData = (data) => {
  return farmService.filterCurrentFarmData(data);
};

/**
 * 为API请求添加场站参数
 * @param {Object} params - 原始参数
 * @returns {Object} - 包含场站参数的参数对象
 */
export const addFarmParams = (params = {}) => {
  return farmService.addFarmParams(params);
};

/**
 * 获取当前场站代码
 * @returns {string} - 当前场站代码
 */
export const getCurrentFarm = () => {
  return farmService.getCurrentFarm();
};

/**
 * 设置当前场站
 * @param {string} farmCode - 场站代码
 */
export const setCurrentFarm = (farmCode) => {
  farmService.setCurrentFarm(farmCode);
};

/**
 * 监听场站变化
 * @param {Function} callback - 回调函数
 */
export const onFarmChange = (callback) => {
  farmService.addListener(callback);
};

/**
 * 移除场站变化监听器
 * @param {Function} callback - 回调函数
 */
export const offFarmChange = (callback) => {
  farmService.removeListener(callback);
};