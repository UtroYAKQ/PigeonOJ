# 前端重构方案：Astro + shadcn/ui

> **状态**：提案（尚未并入产品契约）
> **分支**：`refactor/astro-shadcn-frontend`
> **脚手架**：`src/frontend-astro/`（旧 Vue 前端 `src/frontend/` 保持在线，未切换）
> **范围**：前端技术栈与迁移路径；不改后端 API / 表结构 / 权限模型。
> 切换完成后，本文件的有效约定并入 [`docs/frontend.md`](frontend.md)，并同步
> [`docs/architecture.md`](architecture.md) 的技术栈表与 [`docs/operations.md`](operations.md) 的命令。

## 1. 目标与边界

把 `src/frontend/`（Vue 3 + Pinia + Naive UI + Tailwind v4，47 个页面视图）重构为
**Astro + React 岛屿 + shadcn/ui + Tailwind CSS v4**，并满足：

- 完整覆盖后端 `/api/v1` 的 **151 个已实现端点**（users / files / problems / judge /
  problem-sets / contests / teams / admin）对应的前端能力；
- 保留 `{ code, message, data }` 信封、`Bearer` 鉴权、`Accept-Language` 语言协商、
  统一错误码与权限语义；
- 保留现有 URL 语义与四类业务上下文（题库 / 题单 / 比赛 / 团队）的 **限界上下文隔离**；
- 保留中文 / 英文即时切换、明暗主题、Markdown + KaTeX、Monaco 代码编辑、危险操作二次确认；
- 不实现 `community`（通知 / 私信 / 题解 / 讨论 / 评论）与 AI 能力：后端当前**没有**
  对应模型与路由，不在本次范围。

## 2. 方案摘要

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 渲染模式 | Astro **静态输出（`output: "static"`）** + 多页路由 | 与现有 nginx 静态部署一致；无需 Node 常驻；公开题面后续可加 SSR |
| 交互 | React 19 岛屿，按需 `client:load` / `client:idle` / `client:visible` | 只有编辑器、表格、弹窗等需要水合；其余零 JS |
| 组件 | shadcn/ui `radix-nova` 预设（Radix primitives + lucide） | 源码可控、可访问性基线好、与 Tailwind 令牌一致 |
| 样式 | Tailwind v4 + CSS 语义令牌 | 与旧前端色板 / 圆角 / 暗色对齐 |
| 跨岛状态 | **nanostores**（`@nanostores/react`） | Astro 官方推荐的跨岛方案；React Context 无法跨岛 |
| 服务端状态 | TanStack Query v5（共享 QueryClient 模块） | 分页 / 缓存 / 轮询 / 失效重拉；评测与榜单轮询友好 |
| 表格 | TanStack Table + shadcn Table | 替代 Naive UI `n-data-table`，排序 / 筛选 / 列定义可控 |
| 表单 | react-hook-form + zod + shadcn Form | 校验规则与后端 Pydantic 约束对齐 |
| 路由 | Astro 文件路由（MPA） | 天然按页面拆包；URL 即状态 |
| i18n | 轻量 i18n 模块 + nanostores（**不改 URL**） | 保留现有链接与即时切换；Astro 内置 i18n 会引入语言前缀 |
| 鉴权 | 客户端 `Bearer` Token + 守卫岛 | 静态站无法在服务端读 localStorage；数据安全由后端 API 兜底 |
| 迁移方式 | 并行迁移（strangler），按路由逐块替换，最后切 nginx | 可随时回滚；旧前端保持可用 |

**明确不做**：不做 SPA 全量客户端路由；不引入 Next.js；不引入新的后端 BFF；
不做 WebSocket / SSE 实时推送（沿用轮询）；不把业务权限判断下放到前端（前端只做显隐）。

## 3. 已完成的脚手架

`src/frontend-astro/` 已可运行、可构建：

- Astro 7.4 + `@astrojs/react` + React 19 + TypeScript 严格模式
- Tailwind CSS v4（`@tailwindcss/vite`，无 `tailwind.config`）
- shadcn/ui CLI 4.x，`components.json` 预设 `radix-nova`，已安装 24 个基础组件：
  button / card / input / label / badge / table / tabs / dialog / dropdown-menu /
  select / textarea / checkbox / switch / separator / skeleton / avatar / tooltip /
  breadcrumb / pagination / sonner / spinner / empty / sheet / sidebar
- 品牌令牌：主色 `#f4511e`（暗色 `#ff7043`）、语义色 success / warning / info /
  destructive、6px 圆角、亮暗双套
- 主题切换（亮 / 暗 / 跟随系统，localStorage `pigeonoj.theme`，首屏内联脚本防闪烁）
- `/api` 开发代理（`API_PROXY_TARGET` > `SERVER_PORT` > 8000）
- 验证页 `/`：按钮 / 表单 / 表格 / 弹窗 / Toast / Tabs / 状态色板（**仅脚手架演示，不接业务**）
- 质量门禁：`npm run check` / `lint` / `format:check` / `build` 全绿
- 部署预置：`Dockerfile` + `nginx.conf`（**尚未接入 compose**）

## 4. 目标架构

### 4.1 渲染模式：先静态，按需 SSR

| 方案 | 优点 | 代价 | 结论 |
| --- | --- | --- | --- |
| 静态 MPA（推荐） | 部署不变、CDN 友好、首屏快、无 Node 运行时 | 鉴权只能客户端守卫；题面 SEO 需额外处理 | **一期采用** |
| Node SSR（`@astrojs/node`） | 服务端读 Cookie、首屏直出、SEO 好 | 新增 Node 服务 / 反向代理 / 会话改造；与现有 nginx 部署冲突 | 二期按 SEO 需求评估 |

静态模式下，页面 HTML 对所有访客相同；私有数据一律由登录后的客户端请求获取，
后端仍是唯一鉴权边界。**不要在 HTML 中预渲染任何用户数据。**

### 4.2 目录结构（建议）

```text
src/frontend-astro/src/
  components/
    ui/                  # shadcn 组件（CLI 生成）
    layout/              # 应用壳：sidebar / header / breadcrumb / user-menu
    problem/             # 题面、双栏工作台、样例、测试点编辑器、SPJ 编辑器
    submission/          # 状态标签、测试点明细、轮询
    contest/             # 榜单、公告、赛时工具
    team/                # 团队成员 / 申请 / 空间卡片
    admin/               # 配置表单、日志表格、导入导出
  hooks/                 # use-theme / use-mobile / use-polling / use-session
  layouts/
    main.astro           # 应用壳（登录后）
    auth.astro           # 登录 / 注册 / 邀请落地的无壳布局
  lib/
    api/                 # 按域拆分的 API 客户端（users / problems / judge …）
    stores/              # nanostores：session / site-config / locale / theme
    query.ts             # 共享 QueryClient
    envelope.ts          # { code, message, data } 解包与 ApiError
    i18n/                # 词典 + locale store
    markdown/            # Markdown + KaTeX 渲染
    theme.ts
  pages/                 # 文件路由（见 4.4）
  styles/global.css      # Tailwind + 设计令牌
```

### 4.3 岛屿划分原则

| 场景 | 指令 | 说明 |
| --- | --- | --- |
| 首屏可见且必须可交互（登录表单、主页操作） | `client:load` | 立即水合 |
| 首屏之下 / 次要交互（页脚、折叠面板） | `client:idle` 或 `client:visible` | 降低 TBT |
| 必须依赖 `window` / 第三方 DOM 库（Monaco） | `client:only="react"` | 放弃 SSR，避免 hydration 不一致 |
| 纯展示（题面静态部分、页头、面包屑） | 无指令 | Astro 渲染，零 JS |

原则：**一个页面只保留 2–4 个岛屿**。表格 + 筛选 + 分页放进同一个岛屿，
避免每个按钮一个 React 根。主题切换这类跨页状态用 nanostores 同步。

### 4.4 路由与上下文隔离

Astro 文件路由直接映射旧 URL；动态段用 `[id].astro` / `[...slug].astro`：

```text
src/pages/
  index.astro
  login.astro  register.astro  verify/[token].astro
  user/profile.astro  user/security.astro  user/sessions.astro
  problems/index.astro  problems/[id].astro
  problems/[problemId]/submissions/[sid].astro
  problem-sets/index.astro  problem-sets/[setId]/index.astro
  problem-sets/[setId]/problems/[problemId].astro
  problem-sets/[setId]/problems/[problemId]/submissions/[sid].astro
  contests/index.astro  contests/[cid]/index.astro
  contests/[cid]/problems/[problemId].astro
  contests/[cid]/problems/[problemId]/submissions/[sid].astro
  contests/[cid]/submissions/[sid].astro
  teams/mine.astro  teams/invites/[token].astro  teams/[teamId]/index.astro
  teams/[teamId]/problems/[problemId].astro
  teams/[teamId]/sets/[setId]/index.astro
  teams/[teamId]/sets/[setId]/problems/[problemId].astro
  teams/[teamId]/contests/[cid]/index.astro
  teams/[teamId]/contests/[cid]/problems/[problemId].astro
  teams/[teamId]/contests/[cid]/submissions/[sid].astro
  admin/**             # 与旧 admin 路由一一对应
```

**上下文参数化**：题目工作台、评测结果等复用组件接收 `context` 配置对象，
而不是在组件里判断 URL 前缀：

```ts
type ProblemContext =
  | { kind: "pool" }
  | { kind: "set"; setId: string }
  | { kind: "contest"; contestId: string }
  | { kind: "team"; teamId: string }
  | { kind: "teamSet"; teamId: string; setId: string }
  | { kind: "teamContest"; teamId: string; contestId: string }
```

配置对象集中声明：详情端点、交题端点、自测端点、提交详情端点、返回链接、
面包屑父链。**禁止跨上下文跳转**（题单内交题不得跳 `/problems/:id`），
上下文专属端点按 `docs/frontend.md`「路由上下文隔离」执行。

Astro 默认目录格式会生成尾斜杠 URL（`/problems/`）。二选一：

- 保留尾斜杠，nginx `try_files $uri $uri/index.html`；
- 或设置 `trailingSlash: "never"` + `build.format: "file"`，nginx 增加 `$uri.html`。

迁移期建议先保留尾斜杠，切 nginx 时统一 301（避免旧链接 404）。

### 4.5 认证与权限

- Token：`localStorage["pigeonoj.token"]`（与旧前端同名，便于双站并行调试）；
  请求头 `Authorization: Bearer <token>`，同时携带 `Accept-Language`。
- `GET /users/me` 恢复会话；401（2001/2002）清除 Token 并跳 `/login?redirect=…`。
- 页面守卫：`layouts/main.astro` 挂一个 `SessionGate` 岛屿（`client:load`），
  未登录时重定向；`/login`、`/register`、`/verify/:token`、`/`、`/problems`、
  `/problem-sets`、`/contests` 等公开页不阻塞。
- 角色显隐：`roles` 来自 `UserPublic.roles`；`admin` / `tutor` 的菜单差异、
  `can_manage` / `can_view_problems` / `can_submit` 等能力位以接口返回为准，
  前端只做入口显隐，**不做权限放行**。
- 提交 / 危险操作二次确认；删除账号需密码；封禁 / 冻结需原因与时长。

### 4.6 数据层

- `lib/envelope.ts`：统一解包 `{ code, message, data }`；`code !== 0` 抛 `ApiError`
  （携带 `code` / HTTP 状态）。错误文案优先用后端 `message`（后端已按
  `Accept-Language` 翻译），网络异常 / 结构异常回退本地 i18n 文案。
- `lib/api/<domain>.ts`：按后端模块拆分，函数签名带 TypeScript 类型
  （可由 OpenAPI `/openapi.json` 生成 `types/api.d.ts`，减少手写漂移）。
- TanStack Query：
  - Query key 约定 `[domain, 'list'|'detail', params]`；
  - 列表 `placeholderData: keepPreviousData` 避免翻页闪烁；
  - 评测详情 / 榜单用 `refetchInterval`，在 `document.visibilityState === "hidden"`
    时暂停；页面卸载自动停止；
  - 变更后 `invalidateQueries` 精确失效（如交题后失效提交列表与该题计数）。
- 分页契约：`page` / `page_size ≤ 100`；搜索手动触发（输入不自动请求），
  清空关键词立即重查——沿用旧交互。

### 4.7 状态与「页面缓存」替代

旧前端用 `KeepAlive` 保留列表筛选 / 页码 / 滚动位置。Astro MPA 默认不保留，替代方案：

1. **URL 即状态**：筛选、页码、tab、难度区间全部写入 query string；
   返回时浏览器前进/后退恢复同一 URL。这是首选，且可分享。
2. **草稿持久化**：代码编辑器内容存 `localStorage`（沿用旧 `useCodeDraft` 语义），
   切题 / 刷新不丢。
3. **会话级 store**：站点配置、登录用户、语言、主题放 nanostores；
   页面间不重复拉取 `site-config` / `users/me`。
4. **滚动恢复**：`<ClientRouter />`（View Transitions）或浏览器原生 scroll restoration；
   评测结果等轮询页在 `visibilitychange` 时暂停。

> 有意放弃「组件实例缓存」：MPA 下页面切换必然重新挂载。验收时以
> 「URL 恢复筛选 + 草稿不丢 + 不重复请求静态配置」为准，而不是逐页比对 KeepAlive。

### 4.8 国际化

- 保留 **zh-CN / en-US 即时切换、URL 不变**；语言存 `localStorage`，并同步
  `<html lang>` 与请求头 `Accept-Language`。
- 词典按命名空间拆分（app / problems / contests / teams / admin / user / home），
  与旧 `src/frontend/src/i18n/locales/` 的 key 对齐，便于逐页迁移与缺失检查。
- 方案对比：
  - **i18next + react-i18next**：生态成熟、支持插值 / 复数 / 命名空间；Astro 静态部分
    用同一实例的服务端 `t()`。**推荐**。
  - 轻量自研 store：零依赖，但插值 / 复数 / 按需加载要自己补。
  - Astro 内置 i18n：会引入 `/{locale}/` 前缀，改变现有链接，**不采用**。
- 质量门禁：移植 `scripts/check-i18n-keys.mjs` 的 key 对齐检查（zh / en 必须同键）。
- 用户可见文案零硬编码；日期 / 数字用 `Intl` 并按 locale 格式化。

### 4.9 主题与设计令牌

- 令牌唯一来源：`src/styles/global.css` 的 `:root` / `.dark`；
  业务组件禁止硬编码色值，使用 `bg-card` / `text-muted-foreground` / `text-success` 等语义类。
- 状态色：`success`（AC）、`warning`（TLE / 封榜）、`destructive`（WA / 危险）、
  `muted`（Pending / 未提交）、`info`（比赛 / 提示）。
- 暗色：`html.dark` + `@custom-variant dark`；Monaco / KaTeX 主题同步切换。
- 站点默认主题（`site.default_theme`）只影响首次访问的初始值，用户选择优先。

### 4.10 Markdown、KaTeX 与编辑器

| 能力 | 旧实现 | 新方案 |
| --- | --- | --- |
| Markdown 渲染 | markdown-it + DOMPurify + KaTeX | `react-markdown` + `remark-gfm` + `remark-math` + `rehype-katex` + `rehype-sanitize`（SSR / CSR 均可） |
| 公式 | `$...$` / `$$...$$` | `remark-math` + `katex/dist/katex.min.css` |
| Markdown 编辑 | md-editor-v3（**Vue 专用，不可复用**） | `@uiw/react-md-editor`（CodeMirror 6）或自研 textarea + 预览分栏 |
| 代码编辑器 | Monaco（自建主题 / 补全） | `@monaco-editor/react`，`client:only="react"`，迁移现有 `monaco/theme.ts`、`completions.ts` |
| 插图 | `POST /files/upload/image` + `![](url)` | 同端点；编辑器工具栏粘贴 / 上传，限宽 50% |

题面字段：背景（必填，渲染在题面前）、题面、输入说明、输出说明、题面说明
（可选，渲染在最后）、官方题解（仅管理者可见）。**禁止对用户可控内容直接 `v-html`**。

### 4.11 表格、表单与反馈

- 列表统一：`SearchFilterBar`（关键词 + 筛选 + 手动「查询」+ 刷新按钮）
  + `DataTable`（TanStack Table）+ 底部分页；空态、加载态、错误态三态齐全。
- 表单：`label` 置顶、必填标记、提交 loading、错误信息贴近字段；
  日期时间统一本地时区展示，提交 ISO 8601。
- 反馈：`sonner` Toast（成功 / 失败 / 进行中）；危险操作用 `Dialog` 二次确认；
  需要输入的（封禁原因、注销密码、冻结时长）用带表单的 Dialog。
- 刷新按钮：icon-only，加载中图标自旋，`aria-label` 明确。

### 4.12 性能与可访问性

- Monaco、Markdown 编辑器、图表等重依赖只在需要的页面加载；Monaco 用
  `client:only` + 动态 import，避免进入主包。
- 图片：题面插图 / 头像使用后端不可变 URL（`Cache-Control: immutable`），
  轮播只加载当前 + 相邻帧（沿用旧首页策略）。
- 路由级代码分割由 Astro 自动完成；第三方依赖按页面拆分。
- 可访问性：图标按钮必须有 `aria-label`；状态不只靠颜色；键盘可达；
  弹窗焦点锁定；对比度满足 WCAG AA（主色按钮小字号需检查）。

### 4.13 错误与可观测性

- 统一错误出口：`ApiError` → Toast / 页面错误态；401 跳登录；403 提示无权限；
  404 显示空态而不是白屏；429 提示冷却 / 限流。
- 下载类接口（FPS 导出）是 `blob` 原始响应：成功直接保存，失败需解包 JSON 信封。
- 每条响应带 `X-Request-Id`；错误 Toast 可展示该 ID 便于排查（可选）。
- 前端异常边界：每个岛屿包 `ErrorBoundary`，避免单点错误导致整页空白。

## 5. 迁移阶段与工作量

> 工作量为单人估算，含自测与文档同步，不含后端改动。

| 阶段 | 内容 | 出口标准 | 估算 |
| --- | --- | --- | --- |
| **P0 骨架**（已完成） | Astro / shadcn / Tailwind / 令牌 / 主题 / 代理 / 验证页 | `check` + `lint` + `build` 通过 | 1–2 天 |
| **P1 壳层与账号** | 应用壳、站点配置、首页、登录 / 注册 / 找回、用户中心、会话、i18n 框架 | 公开页与账号链路可用；双语 + 亮暗 + 窄屏 | 4–6 天 |
| **P2 题库与判题** | 题目列表 / 详情双栏 / 交题 / 自测 / 评测结果 / 提交历史 / 写题向导 / 测试点 / SPJ / 验题 / 发布 / FPS 导入导出 | 出题 → 验题 → 发布 → 作答 → 评测闭环 | 10–14 天 |
| **P3 题单与比赛** | 题单中心 / 详情 / 管理 / 编排；比赛中心 / 详情 / 报名 / 榜单 / 提交 / 建赛 / 赛时工具 / 滚榜 | ACM / IOI 计分、封榜解冻、上下文隔离 | 10–14 天 |
| **P4 团队空间** | 团队中心 / 邀请 / 详情 / 成员与申请；团队题库 / 题单 / 比赛全部上下文路由 | 引用快照、可见性、团队门控 | 10–14 天 |
| **P5 管理后台** | 用户 / 在线 / 提交面板 / 标签 / 配置 / 日志 / 沙箱 / 举报 / 比赛 / 题单 / 团队只读 | admin 与 tutor 菜单差异、配置掩码、日志导出 | 8–12 天 |
| **P6 收口** | 全量回归、i18n / a11y / 性能、Docker 与 compose 切换、删旧前端、文档合并 | 与旧前端功能对齐；可回滚 | 4–6 天 |

合计约 **47–68 个工作日**（单人）；可并行时按模块拆分。

## 6. 需要实现什么（按后端模块）

> 后端已实现、前端待实现。权限以 `docs/security.md` 与各 `docs/contracts/` 为准；
> 下表「端点」为后端实际路由（151 个中的相关子集），前端只调用、不改契约。

### 6.1 认证与用户中心（13 个端点）

| 页面 | 端点 | 必须实现的行为 |
| --- | --- | --- |
| `/login` | `POST /auth/login` | 邮箱 + 密码；失败次数超限提示冻结；登录后存 Token 并回跳 `redirect`；`Accept-Language` |
| `/register` | `POST /auth/email-code`、`POST /auth/register` | 注册开关（`site.register_enabled=false` → 2005）；邮箱验证开关；验证码 60s 倒计时；密码 / 昵称校验 |
| 找回密码 | `POST /auth/email-code`（reset_password）、`POST /auth/reset-password` | 验证码一次性；重发间隔 4001 |
| `/user/profile` | `GET/PUT /users/me`、`POST /files/upload/avatar` | 昵称 / 签名 / 头像 / 主题；头像 ≤2MB、JPG/PNG/WEBP/GIF；上传频控 4002 |
| `/user/security` | `POST /auth/change-password`、`POST /auth/change-email`、`DELETE /users/me` | 旧密码校验；换绑邮箱验证码；注销需密码 + 二次确认 |
| `/user/sessions` | `GET /users/me/sessions`、`DELETE /users/me/sessions/{sid}`、`DELETE /users/me/sessions` | 当前 / 在线标记、设备 / IP / 最近活跃；撤销单条；下线其他设备 |
| `/verify/[token]` | `GET /verify-invites/{token}`、`POST /problems/{id}/verify` | 公开解析邀请；展示题面与样例；提交验题代码（任意登录用户） |
| 全局 | `POST /auth/logout`、`GET /site-config` | 登出清 Token；站点名 / Logo / ICP / 注册开关 / 默认主题 / 海报 / 公告 |

错误重点：`2001/2002/2003/2004/2005`、`3002`（邮箱已注册 / 冻结封禁）、
`4001`（验证码频控）、`4002`（登录锁定 / 上传频控）、`1001`。

### 6.2 首页与站点壳层

| 能力 | 数据源 | 说明 |
| --- | --- | --- |
| 站点名 / Logo / ICP | `GET /site-config` | 未配置回退默认；标题「页面 · 站点名」 |
| 首页海报轮播 | `site.banners[{image,title,link}]` | 仅当前 + 相邻帧加载；无海报回退品牌横幅 |
| 系统公告 | `site.announcement`（Markdown） | 空则弱化占位 |
| 快捷入口 | 静态路由 | 题库 / 题单 / 比赛 / 团队 |
| 侧栏 / 顶栏 / 面包屑 | 角色 + 路由 | admin / tutor 菜单差异；面包屑只反映真实层级 |
| 主题 / 语言 / 用户菜单 | 本地 + `users/me` | 头像菜单含设置 / 管理后台 / 退出 |

### 6.3 题库与判题（problems 16 + judge 9 + files 4）

| 页面 | 端点 | 必须实现的行为 |
| --- | --- | --- |
| `/problems` 题库列表 | `GET /problems`、`GET /problems/tags` | 分页；关键词；标签；难度闭区间；`scope=all` 仅 published+public；`mine=true` 仅本人已发布；登录后 `solved` 状态；通过率现算（`accepted_count/submission_count`，0 显示 `--`） |
| `/problems/[id]` 双栏工作台 | `GET /problems/{id}`、`GET /problems/{id}/submissions`、`POST /submissions`、`POST /problems/{id}/run-code` | 题面 Markdown + KaTeX；样例复制 + 解释；语言切换不覆盖代码；提交二次确认；自测 stdin/stdout；草稿持久化；SPJ 徽标；窄屏上下堆叠、比例持久化 |
| 评测结果 | `GET /submissions/{id}`（本人） | 2s 轮询、约 5 分钟停止并提示手动刷新；状态 / 分数 / 耗时 / 内存；编译错误；逐测试点明细（状态 / 耗时 / 内存 / 得分 / 输出 / SPJ message）；**不展示期望输出**；ACM 不展示 IOI 部分分 |
| 提交历史 | `GET /submissions` | 按题目 / 状态 / 分页筛选；仅本人 |
| 写题向导（3 步） | `POST /problems`、`PUT /problems/{id}`、`PUT /problems/{id}/samples`、`GET/PUT/PATCH /problems/{id}/test-cases`、`POST .../test-cases/apply`、`GET/PUT/DELETE /problems/{id}/spj` | 题面必填；样例 ≤10 组、单项 ≤64KB；测试点 ≤1000、单侧 ≤8MB；ZIP 前端解压为可编辑内容；PATCH 行级 diff；暂存集 / 生效集状态；SPJ 源码 ≤256KB；未验题 / 有暂存 / 样例过期禁止发布（3002） |
| 验题与发布 | `POST /problems/{id}/verify`、`GET /problems/{id}/verify/invite`、`POST .../publish`、`POST .../archive` | 发起邀请（小时数）；任意登录用户提交验题代码；验题通过仅置「已验待生效」；显式 apply 才晋升；发布校验 active ≥1；归档 |
| 题目管理列表 | `GET /problems?scope=mine` | admin 全量、tutor 仅本人；status / ownership 过滤；`needs_reverification`；草稿 / 归档；行点击只读预览（不跳前台） |
| 题目管理提交 | `GET /problems/{id}/submissions`、`GET /problems/{id}/submissions/{sid}` | 全员提交；状态 / 昵称 / 语言 / 提交类型筛选；详情轮询；权限 `can_manage` |
| FPS 导入 / 导出 | `POST /admin/problems/import`、`GET /admin/problems/{id}/export`、`GET /admin/problems/export?ids=` | ZIP / XML 上传 ≤20 题；逐题结果列表；勾选跨页保留；单题 XML / 批量 ZIP 附件下载（blob，错误解包信封） |
| 用户自测 | `POST /problems/{id}/run-code` | 单次运行、不落库；≤64KB；冷却 4001；无节点 / 超时 5001 |

隐藏约束：详情接口不返回测试点与题解（题解仅管理者）；测试点内容仅管理者可读；
提交结果不含期望输出；题目限制以 C++ 为基准，其他语言按 `sandbox_configs` 比例展示有效限制。

### 6.4 题单（8 个端点）

| 页面 | 端点 | 必须实现的行为 |
| --- | --- | --- |
| `/problem-sets` 题单中心 | `GET /problem-sets` | 仅公开未下线；`mine=true` 含本人私有（须登录） |
| `/problem-sets/[setId]` 详情 | `GET /problem-sets/{id}` | 按 `sort_order`；题目元信息 + `solved`；`can_manage` 入口 |
| 题单内题目 / 交题 | `GET /problem-sets/{id}/problems/{pid}`、`POST .../submissions` | **上下文内专用端点**，不跳题库；题目不属于题单 3001 |
| 题单管理 | `POST /problem-sets`、`PUT /problem-sets/{id}`、`PUT .../items`、`POST .../archive`、`GET /admin/problem-sets` | 公开 / 私有；编排全量替换（重复 3003，不可见 1001）；下线不删除；管理端只读预览 |

### 6.5 比赛（19 个端点）

| 页面 | 端点 | 必须实现的行为 |
| --- | --- | --- |
| `/contests` 比赛中心 | `GET /contests`、`GET /contests/me` | 卡片流（logo / 状态 / 赛制 / 题数 / 报名数 / 时间窗）；「我的比赛」 |
| `/contests/[cid]` 详情 | `GET /contests/{id}`、`POST .../register` | Hero + 时间轴 + Markdown 说明 + 公告；报名；`can_register/can_view_problems/can_submit` 能力位；题目 / 榜单 / 提交三 tab 的赛前 / 赛中 / 赛后显隐 |
| 比赛内题目 | `GET /contests/{id}/problems`、`GET .../problems/{pid}`、`POST .../submissions` | 赛中已报名、赛后所有登录用户；未报名仅公开题；赛后补题标记 `is_after_contest`（不计榜）；不跳出比赛上下文 |
| 榜单 | `GET /contests/{id}/board`、`GET .../board/{uid}/{pid}/accepted` | ACM / IOI 两套列；封榜冻结提示；点击 AC 格查看成功提交（赛后 / 管理角色） |
| 比赛提交 | `GET /contests/{id}/submissions`、`GET .../submissions/{sid}` | 管理角色随时；非管理赛中隐藏、赛后开放；筛选 / 详情 |
| 建赛 / 编辑 | `POST /contests`、`PUT /contests/{id}`、`GET .../problems/search` | 时间四元组校验；封榜时间；题目编排 ≤26；logo 上传；`status != scheduled` 时 PUT 3002 |
| 赛时工具 | `PUT .../announcement`、`POST .../extend`、`PUT .../freeze-time`、`POST .../unfreeze`、`GET .../scoreboard-show` | 公告 Markdown；延时只能更晚；封榜时间可改 / 取消；解冻仅赛后；滚榜数据只读 |
| 滚榜大屏 | `scoreboard-show` | 独立静态页，按 `base_rows → steps → final_rows` 回放；当前旧实现 `public/scrollboard.html` 可先保留 |

### 6.6 团队（50 个端点，含团队空间）

| 页面 | 端点 | 必须实现的行为 |
| --- | --- | --- |
| `/teams/mine` 团队中心 | `GET /teams`、`GET /teams/mine` | 公开团队卡片墙 + 「我的团队」；非成员申请入口；私有团队仅邀请链接 |
| `/teams/invites/[token]` | `GET /teams/invites/{token}`、`POST /teams/{id}/applications` | 公开解析；登录后申请 |
| `/teams/[teamId]` 详情 | `GET /teams/{id}`、`GET .../members`、`GET .../applications`、`POST .../review`、`POST .../invites`、`POST .../exit`、`DELETE .../{uid}`、`POST .../{uid}/admin`、`PUT .../note`、`DELETE /teams/{id}`、`PUT /teams/{id}` | 五个 tab：成员 / 题库 / 题单 / 比赛 / 申请；角色显隐（creator / admin / member）；邀请链接；审批；备注；踢出 / 退出 / 解散 |
| 团队题库 | `GET /teams/{id}/problems`、`POST .../references`、`GET .../referenceable`、`GET .../arrangeable`、`GET .../problems/{pid}`、`POST .../submissions`、`POST .../run-code` | 引用 = 快照复制；`referenced_at`；成员仅 team_visible，管理另见 admin_visible；草稿箱；`needs_reverification` |
| 团队题单 | `GET/POST /teams/{id}/problem-sets`、`PUT .../items`、`POST .../archive`、`GET .../{sid}`、`GET .../problems/{pid}`、`POST .../submissions`、`POST .../run-code` | 可见性 team_visible / admin_visible；`copy_items_from` 快照复制；上下文专用端点 |
| 团队比赛 | `GET/POST /teams/{id}/contests`、`GET/PUT .../{cid}`、报名 / 题目 / 交题 / 榜单 / 提交 / 解冻 / 公告 / 延时 / 封榜 / 滚榜 | 团队成员门；全部走 `/teams/{teamId}/contests/...` 前缀 |
| 团队写题 | 题库 / 题单 / 比赛上下文各自的 `POST /problems`（带 `team_id`）、`PUT .../statement` | 团队直建或引用；权限 team_creator / team_admin |

### 6.7 管理后台（30 个端点）

| 页面 | 端点 | 必须实现的行为 |
| --- | --- | --- |
| `/admin` 首页 | — | 按角色重定向（admin → 用户管理，tutor → 题目管理） |
| 用户管理 | `GET /admin/users`、`PUT .../roles`、`POST .../ban`、`.../unban`、`.../freeze`、`.../unfreeze` | 单一全局角色替换；封禁原因；冻结时长 1–10080 分钟；状态标签 |
| 在线用户 | `GET /admin/users/online` | 10 分钟窗口；同设备去重；15s 轮询；设备 / IP / 归属地 |
| 全站提交 | `GET /admin/submissions` | 提交类型 / 用户 / 题目 / 状态 / 语言筛选；题目预览与评测详情只读 |
| 标签管理 | `GET/POST /admin/tags`、`PUT .../{id}`、`POST .../archive` | 新增 / 改名改色 / 归档；归档保留关联但不可新选 |
| 系统配置 | `GET/PUT /admin/configs` | 分域 tabs：site / auth_email / team / contest / sandbox / log / community；`*.password` 掩码；保存后即时生效 |
| 首页配置 | `PUT /admin/configs` + `POST /files/upload/site-logo` | 海报增删排序、公告 Markdown、Logo 上传 |
| 日志 | `GET /admin/logs/{type}`、`DELETE /admin/logs/{type}` | request / login / exception；关键词 / 昵称 / 时间范围；当前页 CSV；一键清空需二次确认 |
| 沙箱状态 | `GET /admin/sandbox/status` | 节点在线 / 负载 / CPU / 内存 / 任务数 / 容量 / 版本 / 心跳 |
| 举报 | `GET /admin/reports`、`POST .../{id}/handle` | pending / handled / ignored；处理动作 |
| 比赛管理 | `GET /admin/contests`、`POST /contests`、`PUT /contests/{id}`、赛时工具 | admin 全量、tutor 仅本人；`contest_type` 过滤 |
| 题单管理 | `GET /admin/problem-sets` | 全量；`ownership` 来源筛选；只读题目预览 |
| 团队管理 | `GET /admin/teams`、`GET .../{id}`、成员 / 题库 / 题单 / 比赛只读 | admin 全量（含已解散）；不提供维护动作 |

### 6.8 明确不在本次范围

- **社区**：通知 / 私信 / 题解 / 讨论 / 评论 / 举报的**用户侧**页面——后端没有
  `community` 模型与路由（`reports` 仅有 admin 处理端点）。等后端落地后再加。
- **AI**：文档明确「暂缓实现」。
- 第三方 OAuth、邮箱解绑、WebSocket / SSE、子任务加权计分、per-problem 语言限制覆盖。

## 7. 与旧前端的行为差异（需产品确认）

| 项 | 旧前端 | 新方案 | 影响 |
| --- | --- | --- | --- |
| 页面缓存 | `KeepAlive` 保留实例 | MPA + URL 状态 + 草稿持久化 | 返回列表会重新请求；筛选 / 页码从 URL 恢复 |
| URL 尾斜杠 | 无 | Astro 默认有（可配置） | 旧链接需 301 或统一配置 |
| 语言切换 | 即时、URL 不变 | 保持 | 无 |
| 主题 | Naive UI overrides | shadcn CSS 令牌 | 视觉细节变化，需设计走查 |
| 表格 | `n-data-table` | TanStack Table | 列宽 / 固定列 / 空态需重做 |
| Markdown 编辑器 | md-editor-v3 | 需替换（Vue 专用） | 工具栏与预览交互重做 |
| 首页小贴士 | 随机 i18n 文案 | 可保留 / 可删 | 低风险 |
| 落榜自动解冻 | 无（人工） | 保持 | 无 |

## 8. 质量门禁与 CI

每个 PR 至少：

```bash
cd src/frontend-astro
npm run check        # astro check（Astro + TS）
npm run lint         # ESLint
npm run format:check # Prettier
npm run build        # 静态构建
```

补充（P1 起）：

- **单元测试**：Vitest，覆盖 `lib/envelope`、`lib/i18n`、URL 参数解析、状态字典映射、
  API 模块（mock fetch）。
- **端到端**：Playwright，覆盖登录 → 题库 → 交题 → 评测轮询；建题 → 验题 → 发布；
  比赛报名 → 榜单；团队邀请 → 审批。至少 1 条亮色 + 1 条暗色 + 1 条窄屏。
- **i18n**：zh / en key 对齐脚本（移植 `src/frontend/scripts/check-i18n-keys.mjs`）。
- **可访问性**：`@axe-core/playwright` 扫描关键页。
- **视觉**：关键页亮 / 暗 / 窄屏截图存档，人工走查。

## 9. 部署切换

1. **并行期**：旧 `src/frontend` 继续构建；新 `src/frontend-astro` 用独立端口 / 子路径
   （如 `new.example.com`）预发布。
2. **切换**：
   - `docker/docker-compose.yml` 的 `frontend.build.context` 改为 `../src/frontend-astro`；
   - nginx 使用新 `nginx.conf`：`/_astro/` 长缓存、`try_files` 支持目录格式、
     `/api/` 反代、`client_max_body_size 512m`、读写超时 300s；
   - `run-local.bat` 前端启动目录与端口（4321）同步；
   - 根 `README.md` / `docs/operations.md` 命令更新。
3. **回滚**：保留旧镜像 tag 与旧目录一个版本；nginx upstream 切回即可。
4. **清理**：P6 验收通过后删除 `src/frontend`、旧 `public/scrollboard.html`
   （迁移到新站静态资源）、旧 ESLint / Vitest 配置，合并文档。

## 10. 风险与开放决策

| 风险 / 决策 | 说明 | 建议 |
| --- | --- | --- |
| 静态 vs SSR | 静态无法服务端守卫与题面 SEO | 一期静态；若需要题面 SEO / OG，再加 `@astrojs/node` 仅对公开页 SSR |
| i18n 方案 | 自研 / i18next / Astro i18n | i18next，URL 不变 |
| Markdown 编辑器 | md-editor-v3 不可用 | `@uiw/react-md-editor` 或自研；P2 前定稿 |
| shadcn 预设升级 | `radix-nova` 为新预设，CLI 仍在演进 | 锁定 `components.json` 与包版本；组件源码入库，不盲目 `add --overwrite` |
| Astro 7 / React 19 / TS 6 | 版本较新，生态偶有滞后 | 锁定 `package-lock.json`；CI 固定 Node 24 |
| KeepAlive 丢失 | 列表状态不再自动保留 | URL 状态 + 草稿持久化；验收口径调整 |
| Monaco 体积 | 主包过大 | `client:only` + 动态 import + 按语言加载 |
| 团队路由爆炸 | 团队空间 20+ 上下文路由 | 用上下文配置对象 + 共享页面组件，禁止复制粘贴 |
| 社区后端缺失 | 无法实现通知 / 题解 / 讨论 | 不进本次范围；菜单不放入口 |
| 双前端并行 | 两套 i18n / 主题 / 类型漂移 | 迁移期以旧后端契约为准；每迁移一页删除旧页引用，最后统一删除 |

## 11. 验收清单（P6）

- [ ] 151 个后端端点中，所有前端可达能力均有对应页面 / 操作（社区与 AI 除外）
- [ ] 四类上下文（题库 / 题单 / 比赛 / 团队）导航不越界，面包屑正确
- [ ] 权限：admin / tutor / user / team_creator / team_admin / team_member 菜单与操作显隐正确
- [ ] 判题：交题 → 轮询 → 明细 → 编译错误 / SPJ message 展示；ACM / IOI 计分口径正确
- [ ] 出题：题面 → 样例 / 测试点 → SPJ → 验题 → apply → 发布 → 归档
- [ ] 比赛：报名 → 赛内交题 → 榜单 → 封榜 → 赛后解冻 → 滚榜
- [ ] 团队：创建 → 邀请 → 申请 → 审批 → 引用题目 → 团队题单 / 比赛
- [ ] 管理：用户 / 标签 / 配置 / 日志 / 沙箱 / 举报 / 导入导出
- [ ] i18n：zh / en 全量；切换即时；无硬编码
- [ ] 主题：亮 / 暗 / 跟随系统；无闪烁；Monaco / KaTeX 同步
- [ ] 响应式：≥1280 / 768–1279 / <768 三档走查
- [ ] 质量门禁：`check` / `lint` / `format:check` / `build` / 单测 / E2E 全绿
- [ ] 部署：Docker 构建、nginx 路由、`/health`、`/api` 反代、回滚验证
