import { io } from "socket.io-client";

const socket = io("http://127.0.0.1:5000", {
  withCredentials: true,
  transports: ["websocket"]
});

// 连接成功后添加日志监听
socket.on("connect", () => {
  console.log("Connected to WebSocket server");
  socket.on("training_log", (data) => {
    const event = new CustomEvent("new-log", { detail: data });
    window.dispatchEvent(event);
  });
});

export default socket; 