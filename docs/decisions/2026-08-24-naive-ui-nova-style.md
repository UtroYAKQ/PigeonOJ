# 决策：前端迁移至 Naive UI 并采用 vue-fastapi-admin 视觉风格

- 日期：2026-08-24
- 状态：已采纳
- 取代：`docs/decisions/2026-08-24-frontend-notion-style.md`（Notion 风格决策作废）
- 影响范围：`src/frontend/` 全部视图与布局、`assets/main.css`、`package.json`、文档 `docs/frontend.md`、`docs/architecture.md`

## 背景

Notion 风格落地后用户反馈「白色卡片 / 整体风格违和」：米色画布 + 每页一个巨型白卡的结构
更像仪表盘模板而非 Notion，卡片不承载分组信息只留下边框投影噪音。用户决定放弃 Notion
风格，改为对齐开源模板 [vue-fastapi-admin](https://github.com/mizhexiaoxiao/vue-fastapi-admin)
的视觉风格，并明确允许替换组件库框架。

## 决策

### 技术栈变更

- **组件库：Element Plus → Naive UI**（全量引入 `app.use(naive)`，主题经 JS
  `themeOverrides` 注入，无全局 CSS 变量映射层）。
- **图标保留 `@element-plus/icons-vue`**：该包是独立 SVG 组件库，仅作为图标源在
  `n-icon` 中渲染；路由 `meta.icon` 名称与 `layout/icon.ts` 映射不变。
- 其余栈不变：Vue 3 / Vue Router / Pinia / Tailwind CSS v4 / vue-i18n / Monaco。
- 命令式反馈统一走 `utils/feedback.ts` 的 `createDiscreteApi`（`message` / `dialog`），
  替代 ElMessage / ElMessageBox；需要输入的确认（封禁原因、注销密码）用内联
  `n-modal` 实现。

### 布局壳（对齐参考模板）

- 左侧栏：展开 220px / 收起 64px，白色底右边框；头部 Logo（🐦 主色块）+ 主色粗体标题，
  收起时仅图标；`n-menu accordion`，选中项左侧 4px 主色描边。
- 顶栏：白底 60px 下边框；左侧汉堡折叠钮 + 面包屑（<667px 隐藏），右侧语言切换、
  明暗切换、头像菜单。不设访问标签栏（tags view）。
- 内容画布：`#f5f6fb`（暗色 `#101014`），页面内容以白底无边框 `n-card` 承载。
- 窄屏 ≤991px 强制收起侧栏（与参考模板断点一致）；面包屑 <667px 隐藏。
- 原 SectionTabs 二级标签栏删除；管理后台进入后侧栏整体切换为管理菜单 +
  底部「返回前台」，逻辑保持不变。

### 设计令牌

- 主色 `#F4511E`（取自参考模板 theme.json），pressed `#D84315`；
  info `#2080F0` / success `#18A058` / warning `#F0A020` / error `#D03050`。
- CSS 变量（`assets/main.css`）：`--app-primary` / `--app-content-bg` /
  `--app-card-bg` / `--app-chrome-bg` / `--app-border`(#efeff5) / `--app-text*` /
  `--app-muted-bg`；`html.dark` 同名覆盖。Naive 主题对象见 `settings/theme.ts`，
  两处需同步修改。
- 暗色模式仍由 `html.dark` class 驱动（Tailwind / Monaco 同步），同时传给
  n-config-provider 的 `darkTheme`；模式持久化于 localStorage，登录后跟随用户偏好。
- 表格用 `n-data-table`（columns 数组 + render 函数）；标签 type 用 Naive 词表，
  字典层的 `danger` 经 `toNaiveTagType()` 映射为 `error`。

## 反模式（禁止）

- 禁止再引用 Element Plus 组件或 `--el-*` 变量（icons-vue 图标包除外）。
- 禁止绕过 `settings/theme.ts` 直接硬编码主色；新增颜色必须先入令牌表。
- 禁止恢复渐变背景 / translate-scale 动画（沿用原约束）。

## 验收

- `npm run lint:check` / `npm test`（25 用例）/ `npm run build` 全绿。
- 亮暗两套主题、中英文案、窄屏（<991px 侧栏收起）下检查布局壳、题库、题目详情、
  管理后台等关键页面。
