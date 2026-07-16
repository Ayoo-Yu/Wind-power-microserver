# 使用受支持的 Node.js LTS 构建镜像
FROM node:24.15.0-bookworm-slim AS build

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY package*.json ./

# 按锁文件安装依赖
RUN npm ci

# 复制项目源码
COPY . .

# 执行前端质量门禁并生成产物
RUN npm run verify

# 使用 Nginx 运行静态文件
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# 复制自定义Nginx配置
COPY nginx.conf /etc/nginx/nginx.conf

# 暴露端口
EXPOSE 80

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
