# 使用 Node.js 构建镜像
FROM node:18 AS build

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制项目源码
COPY . .

# 构建前端
RUN npm run build

# 使用 Nginx 运行静态文件
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# 复制自定义Nginx配置
COPY nginx.conf /etc/nginx/nginx.conf

# 暴露端口
EXPOSE 80

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
