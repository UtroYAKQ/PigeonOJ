# PigeonOJ 前端（Astro）

PigeonOJ 前端重构工作区：**Astro + React 19 + shadcn/ui + Tailwind CSS v4**。
旧 Vue 前端仍在 `src/frontend/` 运行，本目录是并行迁移目标，尚未接入
`docker/docker-compose.yml` 与 `run-local.bat`。迁移方案与页面清单见
[`docs/frontend-astro-migration.md`](../../docs/frontend-astro-migration.md)；
日常开发、API 约定、分支与 PR 流程见 [`DEVELOPING.md`](DEVELOPING.md)。

## 技术栈

| 类别 | 选型                                                           |
| ---- | -------------------------------------------------------------- |
| 框架 | Astro 7（静态输出，MPA + React 岛屿）                          |
| 交互 | React 19（`@astrojs/react`）                                   |
| 样式 | Tailwind CSS v4（`@tailwindcss/vite`）                         |
| 组件 | shadcn/ui（`radix-nova` 预设，Radix primitives + lucide 图标） |
| 语言 | TypeScript 严格模式（`astro/tsconfigs/strict`）                |

## 快速开始

```bash
cd src/frontend-astro
npm install
npm run dev          # http://localhost:4321
```

开发服务器把 `/api` 代理到后端，端口链与旧前端一致：

```bash
SERVER_PORT=8000 npm run dev                 # 默认 8000
API_PROXY_TARGET=http://localhost:9000 npm run dev   # 显式覆盖
```

## 命令

| 命令                                      | 说明                                       |
| ----------------------------------------- | ------------------------------------------ |
| `npm run dev`                             | 开发服务器（默认 4321）                    |
| `npm run build`                           | 静态构建到 `dist/`                         |
| `npm run preview`                         | 预览构建产物                               |
| `npm run check`                           | `astro check`：Astro + TypeScript 诊断     |
| `npm run lint` / `npm run lint:fix`       | ESLint                                     |
| `npm run format` / `npm run format:check` | Prettier（含 Astro / Tailwind class 排序） |

## 目录

```text
src/
  components/
    ui/            # shadcn 组件（CLI 生成，可按需改）
    showcase.tsx   # 脚手架验证页（组件 / 主题 / 交互）
    theme-toggle.tsx
  hooks/           # React hooks（主题 / 移动端断点）
  layouts/         # Astro 布局（HTML 外壳、主题首屏脚本）
  lib/             # 无 UI 工具（cn、theme）
  pages/           # Astro 文件路由
  styles/global.css # Tailwind + 设计令牌（亮 / 暗）
```

## 添加 shadcn 组件

```bash
npx shadcn@latest add <component>   # 例：npx shadcn@latest add form
```

组件写入 `src/components/ui/`；`components.json` 已配置 `@/*` 别名与
`radix-nova` 预设。新增组件后跑一次 `npm run format` 统一格式。

## 设计令牌

`src/styles/global.css` 的 `:root` / `.dark` 是与旧前端对齐的语义令牌：

- 主色 `--primary: #f4511e`（暗色 `#ff7043`），语义色 `--success / --warning / --info / --destructive`
- 页面底色 `--background`、卡片 `--card`、边框 `--border`，圆角 `--radius: 6px`
- 暗色由 `html.dark` 驱动；首屏由 `layouts/main.astro` 内联脚本在绘制前应用，
  切换逻辑在 `src/lib/theme.ts`（localStorage key：`pigeonoj.theme`）

业务页面只消费语义令牌，不硬编码色值。

## 当前状态

- ✅ Astro + React + Tailwind + shadcn 初始化完成，24 个基础组件可用
- ✅ 主题（明 / 暗 / 跟随系统）、Toast、Dialog、Tabs、Table 已验证
- ✅ `/api` 开发代理、`astro check` / ESLint / Prettier / 静态构建通过
- ⬜ 业务页面（认证 / 题库 / 判题 / 题单 / 比赛 / 团队 / 管理后台）按迁移方案分阶段实现

首页 `/` 是脚手架验证页，**不包含业务逻辑**，不调用真实接口。
