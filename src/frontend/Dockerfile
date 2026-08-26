# 前端镜像：构建阶段编译 Vue3 应用，运行阶段用 Nginx 托管并反代 /api -> backend:8000
# 构建上下文为 src/frontend（见 docker/docker-compose.yml）

# ---- 构建阶段 ----
FROM node:22-alpine AS build
WORKDIR /app
# 允许部署侧注入 Node 堆限制（小内存机器构建 vue-tsc 需要，如 --max-old-space-size=1536）；
# 不传则用默认值。经 compose build args 或 --build-arg 注入，不在镜像内写死。
ARG NODE_OPTIONS=""
ENV NODE_OPTIONS=${NODE_OPTIONS}
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
