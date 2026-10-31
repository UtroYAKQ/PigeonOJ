# 前端开发指南（Astro 工作区）

> 面向 `src/frontend-astro/` 的日常开发。产品契约见
> [`docs/frontend.md`](../../docs/frontend.md) 与 [`docs/contracts/`](../../docs/contracts/index.md)；
> 迁移方案与页面清单见 [`docs/frontend-astro-migration.md`](../../docs/frontend-astro-migration.md)。

## 0. 仓库与远端

当前约定：

| 远端     | 地址                                         | 用途                |
| -------- | -------------------------------------------- | ------------------- |
| `origin` | `https://github.com/UtroYAKQ/PigeonOJ.git`   | 上游仓库，PR 目标   |
| `mine`   | `https://github.com/2b-creator/PigeonOJ.git` | 你的 fork，推送分支 |

首次克隆 / 新机器（把 `origin` 指向上游、`mine` 指向 fork，与当前工作区一致）：

```bash
git clone https://github.com/2b-creator/PigeonOJ.git
cd PigeonOJ
git remote rename origin mine
git remote add origin https://github.com/UtroYAKQ/PigeonOJ.git
git fetch origin
```

日常同步与推送：

```bash
git fetch origin
git rebase origin/main             # 或 merge，团队内保持一致
git push mine refactor/astro-shadcn-frontend
```

PR 入口（fork → 上游 `main`）：

<https://github.com/UtroYAKQ/PigeonOJ/compare/main...2b-creator:PigeonOJ:refactor/astro-shadcn-frontend?expand=1>

> 迁移分支已推送到 `mine`（你的 fork）。新增功能建议从
> `refactor/astro-shadcn-frontend` 再切 `feat/frontend-xxx` 小分支，PR 目标选
> `refactor/astro-shadcn-frontend`，避免一个 PR 过大。

## 1. 本地启动

### 后端

按仓库根目录 [`docs/operations.md`](../../docs/operations.md) 启动：

```bash
cp .env.example .env                     # 首次
python -m venv .venv                     # 首次
.venv/Scripts/python -m pip install -r src/backend/requirements.txt -r src/backend/requirements-dev.txt
cd src/backend
../../.venv/Scripts/python -m alembic upgrade head
../../.venv/Scripts/python run.py        # http://localhost:8000
```

### 前端

```bash
cd src/frontend-astro
npm install                              # 首次
npm run dev                              # http://localhost:4321
```

`/api` 开发代理的端口链：`API_PROXY_TARGET` > `SERVER_PORT` > `8000`。

```bash
API_PROXY_TARGET=http://localhost:9000 npm run dev
```

打开 <http://localhost:4321/> 应看到脚手架验证页；说明 Astro、Tailwind、shadcn、
React 水合都正常。

## 2. 目录与职责

```text
src/frontend-astro/src/
  pages/                 # Astro 文件路由：一个文件 = 一个 URL
  layouts/               # HTML 外壳（main.astro / 后续 auth.astro）
  components/
    ui/                  # shadcn 组件（CLI 生成，可按需改）
    layout/              # 应用壳：sidebar / header / breadcrumb / user-menu
    problem/             # 题面、双栏工作台、样例、测试点、SPJ
    submission/          # 状态标签、明细、轮询
    contest/             # 榜单、公告、赛时工具
    team/                # 成员、申请、空间卡片
    admin/               # 配置表单、日志表格、导入导出
  hooks/                 # React hooks（主题、断点、轮询、会话）
  lib/
    api/                 # 按域拆分的 API 客户端（P1 落地）
    stores/              # nanostores：session / site-config / locale
    i18n/                # 词典 + locale store（P1 落地）
    theme.ts             # 主题（已实现）
  styles/global.css      # Tailwind + 设计令牌（唯一色值来源）
```

**页面 = Astro 外壳 + React 岛屿**：

- 静态结构、SEO 标题、面包屑、初始骨架用 `.astro`；
- 只有需要交互的区域才挂 React，按需选择指令：

| 指令                  | 适用                               |
| --------------------- | ---------------------------------- |
| `client:load`         | 首屏必须可交互（登录表单、筛选栏） |
| `client:idle`         | 首屏之下的次要交互                 |
| `client:visible`      | 滚动到才需要（长页尾部）           |
| `client:only="react"` | Monaco 等依赖 `window` 的组件      |
| 不写                  | 纯展示，零 JS                      |

原则：**一页 2–4 个岛屿**。表格 + 筛选 + 分页放同一个岛屿，不要每个按钮一个 React 根。

## 3. 新增一个页面（标准流程）

以「题库列表」为例：

1. **先读契约**：`docs/contracts/problems.md` 的端点、权限、错误码、可见性。
2. **建路由**：`src/pages/problems/index.astro`。
3. **写外壳 + 岛屿**：

```astro
---
import MainLayout from "@/layouts/main.astro"
import { ProblemList } from "@/components/problem/problem-list"
---

<MainLayout title="题库">
  <ProblemList client:load />
</MainLayout>
```

```tsx
// src/components/problem/problem-list.tsx
"use client"

export function ProblemList() {
  // 请求、筛选、分页、加载 / 空 / 错误态
  return <div>{/* ... */}</div>
}
```

4. **API 调用**：在 `lib/api/problems.ts` 写类型化函数，页面不直接拼 `fetch`。
5. **四态**：loading / error / empty / success 全部实现；错误用 `sonner` Toast 或页面错误态。
6. **i18n**：所有用户可见文案进词典，zh-CN 与 en-US 同 key；禁止硬编码。
7. **权限**：菜单 / 按钮显隐按接口返回的 `roles` / `can_manage` 等能力位；
   **前端不做权限放行**，越权由后端返回 2003。
8. **自测**：`npm run check`、`npm run lint`、`npm run build`。
9. **同步文档**：新增/改变前端行为时更新 `docs/frontend.md` 或对应 `contracts/`。

## 4. API 客户端约定（P1 首个任务）

当前尚未落地 `lib/api/`；第一个基础 PR 建议按以下约定实现：

```ts
// src/lib/api/http.ts
export class ApiError extends Error {
  constructor(
    readonly code: number,
    message: string,
    readonly httpStatus?: number
  ) {
    super(message)
  }
}

export async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem("pigeonoj.token")
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      "Accept-Language": getLocale(),
      ...init.headers,
    },
  })
  const body = await res.json() // 统一信封
  if (body.code !== 0) throw new ApiError(body.code, body.message, res.status)
  return body.data as T
}
```

约定：

- 统一前缀 `/api/v1`，响应信封 `{ code, message, data }`，`code === 0` 才算成功；
- Token key 与旧前端一致：`localStorage["pigeonoj.token"]`；
- 每个请求带 `Accept-Language`（后端按语言翻译错误 message）；
- 401（2001 / 2002）→ 清 Token、跳 `/login?redirect=...`；
- 403（2003）→ 提示无权限，不吞错；404 / 429 / 5001 分别有明确文案；
- 文件上传用 `FormData`，不要手写 `Content-Type`（浏览器生成 boundary）；
- FPS 导出等 `blob` 下载：成功保存文件；失败响应仍是 JSON 信封，需要解包。

建议按后端模块拆：`lib/api/users.ts`、`problems.ts`、`judge.ts`、`contests.ts`、
`teams.ts`、`admin.ts`、`files.ts`。类型可后续由 `/openapi.json` 生成，先手写。

## 5. 状态与数据

| 数据                              | 方案                                           |
| --------------------------------- | ---------------------------------------------- |
| 登录用户 / 站点配置 / 语言 / 主题 | nanostores（跨岛共享，`lib/stores/`）          |
| 列表筛选、页码、tab               | **URL query string**（可分享、返回可恢复）     |
| 服务器数据                        | TanStack Query（分页、缓存、轮询、失效）       |
| 代码草稿                          | `localStorage`（与旧 `useCodeDraft` 语义一致） |
| 评测 / 榜单轮询                   | `refetchInterval` + 页面隐藏时暂停             |

> Astro 是 MPA，没有 Vue 的 `KeepAlive`。用 URL 状态 + 草稿持久化替代，
> 不要试图在岛屿里实现「页面实例缓存」。

## 6. shadcn 组件

```bash
cd src/frontend-astro
npx shadcn@latest add form          # 例：表单组件
npm run format                      # 统一格式
```

- 组件源码在 `src/components/ui/`，**已入库、可修改**；
- 升级 / 重新生成前先看 diff，避免 `--overwrite` 覆盖本地定制；
- 使用 `cn()`（来自 `cn` 包）合并 className；
- 颜色只用语义类（`bg-card` / `text-muted-foreground` / `text-success`），
  禁止在组件里写死色值；新增令牌加到 `styles/global.css` 的 `:root` 与 `.dark`；
- 深色模式：`html.dark` + Tailwind `dark:`；主题切换用 `lib/theme.ts`。

## 7. i18n 约定

- 词典按命名空间拆分，与旧 `src/frontend/src/i18n/locales/` 的 key 对齐；
- zh-CN / en-US 必须同 key，新增文案两边一起加；
- 语言存 `localStorage`，切换即时生效，**不改 URL**；
- 日期 / 数字用 `Intl.DateTimeFormat` / `Intl.NumberFormat`，按当前 locale；
- 后端错误 message 已按 `Accept-Language` 翻译，优先直接展示。

## 8. Markdown / 代码编辑器

- 题面、公告、题解：`react-markdown` + `remark-gfm` + `remark-math` +
  `rehype-katex` + `rehype-sanitize`（P2 落地）；
- 禁止对用户可控内容使用 `dangerouslySetInnerHTML`；
- 代码编辑器：`@monaco-editor/react`，`client:only="react"`，迁移旧
  `src/frontend/src/monaco/theme.ts` 与 `completions.ts`；
- Markdown 编辑器旧的 `md-editor-v3` 是 Vue 专用，需替换（P2 前定稿）。

## 9. 质量门禁

提交前在 `src/frontend-astro/` 执行：

```bash
npm run check          # astro check（Astro + TS）
npm run lint           # ESLint
npm run format:check   # Prettier
npm run build          # 静态构建
```

后续 P1 起补齐：

```bash
npm test               # Vitest（P1 添加）
npm run test:e2e       # Playwright（P1 添加）
```

至少覆盖：API 信封解包、URL 参数解析、状态字典、i18n key 对齐；
E2E 覆盖登录 → 题库 → 交题 → 评测，出题 → 验题 → 发布，比赛报名 → 榜单。

## 10. Git 与 PR

### 分支

```bash
git checkout -b feat/frontend-problem-list refactor/astro-shadcn-frontend
```

- `feat/frontend-*`：新页面 / 功能
- `fix/frontend-*`：修复
- `chore/frontend-*`：脚手架、依赖、配置
- 迁移总分支：`refactor/astro-shadcn-frontend`

### 提交

建议 Conventional Commits：

```text
feat(frontend): add problem list page
fix(frontend): handle 401 on expired session
chore(frontend): add shadcn form component
```

只提交源码与配置，**不要提交** `node_modules/`、`dist/`、`.astro/`、`.env*`。
提交前 `git status` 确认。

本仓库提交可能开启 GPG 签名；若本机未配置签名，使用：

```bash
git commit --no-gpg-sign -m "..."
```

### 推送与 PR

```bash
git push mine feat/frontend-problem-list
```

然后在 GitHub 打开（base = 上游迁移分支，compare = fork 的功能分支）：

<https://github.com/UtroYAKQ/PigeonOJ/compare/refactor/astro-shadcn-frontend...2b-creator:PigeonOJ:feat/frontend-problem-list?expand=1>

或在 fork 页面点 **Compare & pull request**，把 base 改成
`UtroYAKQ/PigeonOJ:refactor/astro-shadcn-frontend`（或 `main`）。

PR 描述建议包含：

- 对应契约 / 页面清单条目
- 截图（亮 / 暗 / 窄屏）
- 验证命令与结果
- 文档同步情况（`docs/frontend.md` / contracts）

## 11. 下一步（P1 建议顺序）

1. `lib/api/http.ts` + `ApiError` + 单元测试
2. `lib/stores/session.ts`、`site-config.ts`、`locale.ts`
3. `layouts/main.astro` 应用壳：侧栏 / 顶栏 / 面包屑 / 用户菜单
4. `lib/i18n/` 框架 + zh-CN / en-US 基础词典
5. `/login`、`/register`、`/user/profile`、`/user/sessions`
6. `SessionGate` 客户端守卫 + 401 处理
7. Playwright 冒烟：登录 → 首页 → 个人资料

每完成一项单独提交、单独 PR，保持 diff 可 review。
