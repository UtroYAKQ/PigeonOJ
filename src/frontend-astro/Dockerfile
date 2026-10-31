# 新前端镜像（尚未接入 docker/docker-compose.yml；切换时把 frontend 服务 build.context 指向本目录）
# 构建阶段：静态构建 Astro 产物；运行阶段：Nginx 托管 + 反代 /api -> backend:8000

FROM node:24-alpine AS build
WORKDIR /app
# 允许部署侧注入 Node 堆限制（小内存机器）
ARG NODE_OPTIONS=""
ENV NODE_OPTIONS=${NODE_OPTIONS}
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
