// src/composables/useSocket.js
import { io } from 'socket.io-client';

export function useSocket(backendBaseUrl, options = {}) {
  // 设置默认选项并与传入的选项合并
  const defaultOptions = {
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000,
    ...options
  };

  const socket = io(backendBaseUrl, defaultOptions);

  socket.on('connect', () => {
    console.log('Connected to WebSocket server');
  });

  socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
  });

  socket.on('log', (data) => {
    // 检查 data 是否存在以及它是否包含我们预期的字段
    if (!data) {
      console.error('Received data is undefined or null');
      return;
    }

    // 打印 data 的内容，方便调试
    console.log('Received log data:', data);

    // 如果 data 中没有 message 字段，则抛出错误
    if (!data.message) {
      console.error('Received log data is missing "message" field', data);
      return;
    }

    // 如果 data 是有效的，则继续处理
    console.log(data.message);
  });

  socket.on('disconnect', (reason) => {
    console.log(`Disconnected from WebSocket server: ${reason}`);
    
    // 如果是非客户端主动断开连接，尝试手动重连
    if (reason === 'io server disconnect' || reason === 'transport close') {
      socket.connect();
    }
  });

  socket.on('reconnect', (attemptNumber) => {
    console.log(`Reconnected to WebSocket server after ${attemptNumber} attempts`);
  });

  socket.on('reconnect_attempt', (attemptNumber) => {
    console.log(`Reconnection attempt: ${attemptNumber}`);
  });

  socket.on('reconnect_failed', () => {
    console.error('Failed to reconnect to WebSocket server after maximum attempts');
  });

  return socket;
}
