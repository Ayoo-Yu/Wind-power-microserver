import axios from './axios';

// 登录API
export const login = async (username, password) => {
  const response = await axios.post('/api/auth/login', { username, password });
  return response.data;
};

// 获取当前用户信息
export const getCurrentUser = async () => {
  const response = await axios.get('/api/auth/me');
  return response.data;
};

// 修改密码
export const changePassword = async (username, currentPassword, newPassword) => {
  const response = await axios.post('/api/auth/change-password', {
    username,
    current_password: currentPassword,
    new_password: newPassword
  });
  return response.data;
};

// 获取用户列表
export const getUsers = async () => {
  const response = await axios.get('/api/auth/users');
  return response.data;
};

// 创建用户
export const createUser = async (userData) => {
  const response = await axios.post('/api/auth/users', userData);
  return response.data;
};

// 更新用户
export const updateUser = async (userId, userData) => {
  const response = await axios.put(`/api/auth/users/${userId}`, userData);
  return response.data;
};

// 删除用户
export const deleteUser = async (userId) => {
  const response = await axios.delete(`/api/auth/users/${userId}`);
  return response.data;
};

// 重置用户密码
export const resetUserPassword = async (userId, newPassword) => {
  const response = await axios.post(`/api/auth/users/${userId}/reset-password`, {
    new_password: newPassword
  });
  return response.data;
};

// 获取角色列表
export const getRoles = async () => {
  const response = await axios.get('/api/auth/roles');
  return response.data;
}; 