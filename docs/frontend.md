# 前端设计与实现规范

> 本文是 PigeonOJ 前端变更的产品与实现契约。修改 `src/frontend/` 前必须阅读；与 API、数据模型、权限相关的改动仍须同时遵循 `docs/architecture.md` 与对应 `docs/contracts/`。

## 目标与边界

- 前端技术栈固定为 Vue 3、Vue Router、Pinia、Naive UI、Tailwind CSS v4 与 vue-i18n；未经决策记录不得替换或新增同类框架。
- 图标源使用 `@element-plus/icons-vue`（独立 SVG 组件库，在 `n-icon` 中渲染），路由 `meta.icon` 名称见 `layout/icon.ts`。
- 页面服务于编程学习、训练、竞赛和管理场景：信息层级清晰、操作可预期、长时间管理任务易扫描。
- 不以视觉效果牺牲可访问性、移动端可用性、加载性能或既有 RBAC 约束。

## 设计系统（vue-fastapi-admin 风格）

硬约束与决策依据见 `docs/decisions/2026-08-24-naive-ui-nova-style.md`。参考模板：[vue-fastapi-admin](https://github.com/mizhexiaoxiao/vue-fastapi-admin)。

### 色板与令牌

- 主色橙 `#F4511E`（pressed `#D84315`）；info `#2080F0` / success `#18A058` / warning `#F0A020` / error `#D03050`；圆角 3px。
- Naive UI 主题经 `settings/theme.ts` 的 `themeOverrides` 注入，**不使用** CSS 变量映射组件库主题。
- 布局层 CSS 变量唯一来源为 `assets/main.css` 的 `:root` + `html.dark`：
  `--app-primary` / `--app-content-bg`(浅 #f5f6fb · 深 #101014) / `--app-card-bg` /
  `--app-chrome-bg` / `--app-border`(#efeff5) / `--app-text` / `--app-text-secondary` /
  `--app-muted-bg`。组件只允许引用令牌，禁止硬编码色值；修改色板须同步
  `settings/theme.ts` 与 CSS 变量两处。
- 暗色模式由 `html.dark` class 驱动（Tailwind `dark:` 变体、Monaco 主题同步），
  同时传给 `n-config-provider` 的 `darkTheme`；模式持久化 localStorage，
  登录后跟随用户偏好（stores/app + stores/user）。

### 应用壳

1. **侧边栏**：展开 220px / 收起 64px（图标态，Naive 自带 tooltip 显示名称），白底右边框；顶部 Logo 🐦 主色块 + 主色粗体标题（站点名 / Logo 外链来自 `GET /site-config`，经 `stores/app` 驱动；Logo 未配置或非外链时回退默认图标），收起时仅图标；`n-menu accordion` 菜单，选中项左侧 4px 主色描边。窄屏 ≤991px 强制收起。
2. **顶栏**：白底 60px 下边框；左侧汉堡折叠钮 + 面包屑（<667px 隐藏面包屑），右侧语言切换、明暗切换、头像菜单。
3. **内容画布**：浅灰蓝 `--app-content-bg`；页面内容以白底无边框 `n-card` 承载，卡片间距 12–16px。
4. **管理后台空间**：进入 `/admin` 后侧栏整体切换为管理菜单，底部固定「返回前台」；前台业务菜单不出现。`/admin` 面向 staff 会话（admin / tutor）：tutor 仅见「题目管理」，admin 见全部区块（用户 / 配置 / 日志 / 沙箱 / 举报 / 标签）；落地页按角色分流（admin → 用户管理，tutor → 题目管理）。用户设置与管理后台入口都在头像菜单（路由 `meta.hidden`）。
5. **面包屑**：只反映真实层级（如 管理后台/用户管理、题库/题目管理/编辑题目）；首页与顶级区块平级不入面包屑。上下文页经路由 meta 的 `breadcrumbParent` 挂到所属工作台层级下；页面内不设大标题与独立返回按钮，层级回退通过面包屑完成。

### 交互习惯

- **危险与关键操作二次确认**：删除、封禁、注销、提交判题等先确认再执行；确认弹窗用 `utils/feedback.ts` 的 `$dialog.warning`，需要输入的确认（封禁原因、注销密码）用内联 `n-modal`；取消则不发起请求。
- **命令式反馈统一走 `utils/feedback.ts`**（`message` / `dialog`，基于 createDiscreteApi），组件内不得自行再包 MessageProvider。
- **配置多分类横向排布**：系统配置等按域分类的页面用横向 `n-tabs type="line"`。
- 「题面 + 编辑器」类双栏工作台占满视口剩余高度，整页无滚动条、各栏独立滚动；比例持久化 localStorage；窄屏（<900px）退化为上下堆叠；分隔条提供 `role="separator"` 与提示文案。

### 表格工作台

- 筛选 / 搜索 / 导出放在表格上方工具栏，允许换行；表格用 `n-data-table`（columns 数组 + render 函数，列文案随 locale 实时翻译）；行内操作用 `text` 按钮（可配语义色与 14px 图标增强识别，悬停浅底反馈）；分页紧跟表格底部右侧（`n-pagination show-size-picker`）。
- **列表工作台撑满内容画布剩余高度**：根节点用共享类 `page-fill`（视口高 - 顶栏 - 内边距），卡片纵向 flex，表格区 `table-fill` 占满；无数据时空态经 `table-fill-empty` 在表格区域内垂直居中，避免整页松散。
- 字典层标签类型（`constants/dict.ts` TagType 含 `danger`）渲染到 `n-tag` 时必须经 `toNaiveTagType()` 映射（danger → error）。

### 按钮与表单

- 每个操作区域最多一个主按钮；次要操作用 `secondary` / 默认按钮，行内操作用 `text` 按钮。
- 删除、封禁、注销等用 `type="error"`，文案需描述结果。
- 表单 `label-placement="top"`；必填/格式/范围用控件规则和辅助文本表达；提交按钮展示 loading。
- 统一覆盖 loading（`n-spin` / table loading）、error、empty（`n-empty`）、success 状态；错误信息要指向可恢复的下一步。

### 可访问性

- 图标按钮必须有可见文字、`aria-label` 或 `n-tooltip`。
- 不仅依靠颜色传递状态，状态标签应含文本。
- 保持键盘可聚焦顺序；弹窗打开后焦点应留在弹窗内（使用 Naive 标准组件即满足）。

### 题库信息架构（前台消费 / 后台生产）

> 出题入口唯一收敛在管理后台，前台零管理痕迹（见 `docs/decisions/2026-08-24-team-first-problem-production.md`）。

- **题库中心** `/problems/list`（公开）：纯浏览目录 —— 搜索 + 标签筛选 + 目录表格（标题 / 限制），行点击进入题目详情练习。不含任何管理控件与切换器。
- **题目详情** `/problems/:id`：题面 + 编辑器双栏消费页；不提供编辑 / 归档等管理菜单。
- **题目管理** `/admin/problems`（admin / tutor）：管理工作台。状态标签页（全部 / 草稿 / 已发布 / 已归档）+ 搜索；表格列含状态与验题状态标签（需重验时警示），操作列所有状态首列均为「查看」（进入 `/admin/problems/:id/preview` 只读预览），按状态追加动作 —— 草稿：查看 / 编辑；已发布：查看 / 编辑 / 归档；已归档：查看。行点击：草稿 → 编辑向导，已发布 → 预览；已归档行为只读，行点击不跳转（查看走操作列「查看」，避免被带出管理后台）。发布统一在编辑向导第三步完成，列表不提供独立发布入口。
- **标签管理** `/admin/tags`（admin）：题库标签维护页 —— 新建 / 编辑（名称 ≤32 字符 + 可选颜色）/ 归档（确认弹窗；归档不删除，既有题目关联保留展示，但不再可选）；全量列表含已归档（激活在前）。见 `docs/decisions/2026-08-24-remove-difficulty-use-tags.md`。

### 创建 / 编辑向导与验题

> 三步发布流拆为**三个独立路由页面**（见 `docs/decisions/2026-08-25-problem-wizard-pages.md`）：步骤间用路由跳转，可直达、可刷新、浏览器前进后退语义正确；页面内以 `n-steps` 指示当前步骤（不可点击跳步）。

- **第 1 步「基础信息与题面」** `ProblemStatementView.vue`：
  - 新建 `/admin/problems/new`——仅校验题面四要素，保存即创建草稿，成功后 **replace** 进入第 2 步（浏览器后退不回 `/new`，避免重复建草稿）；
  - 编辑 `/admin/problems/:id/edit/statement`（旧链接 `/admin/problems/:id/edit` 301 到此）——保存后 push 进入第 2 步；
  - 表单含标题 / 题面 / 输入输出说明（必填）/ 官方题解（折叠）/ 标签多选（激活标签 ≤8）/ 可见性 / 时限内存。
- **第 2 步「样例与测试点」** `/admin/problems/:id/edit/cases`（`ProblemCasesView.vue`）：展示样例（≤10 组，不参与判题）+ 正式测试点（ZIP 导入或手工编辑）；「下一步」先自动保存（空白草稿行不提交；内容签名与服务器一致时跳过上传，避免纯题面改动误触发重新验题），无任何非空测试点时拦截在本页。
- **第 3 步「验题与发布」** `/admin/problems/:id/edit/verify`（`ProblemVerifyView.vue`，共享组件 `VerifyPublishPanel.vue`）：状态标签（未验题 / 已于 X 通过验题 / 测试点或样例已变更需重新验题）；**自行验题** —— 语言选择 + Monaco 提交代码（先发起空白验题记录，再 `POST /problems/{id}/verify` 提交 `{code, language}`；提交不限身份），判题通过即完成验题并跳评测结果页；或生成邀请链接发给他人验题。底部提供「上一步」与「完成，返回列表」（未发布离开时草稿保留）。
- **发布门禁以后端 `needs_reverification` 为准**：未验题，或测试点 / 样例晚于最近验题通过时间变更 ⇒ 发布按钮禁用（tooltip 说明），后端 publish 同样拒绝（3002）；纯题面改动不影响验题有效性。发布成功回管理工作台。

### 验题邀请落地页

- **验题落地页** `/verify/:token`（公开路由，独立布局）：解析 `GET /verify-invites/{token}` 展示题目概要、题面与样例；未登录引导登录并回跳本页；登录后提供语言选择 + Monaco 编辑器提交验题代码（`POST /problems/{id}/verify` 携带 `invite_token`，`submit_type=verify`），成功后跳评测结果页。链接不返回正式测试点内容与题解。

### 内容渲染与共享样式

- 题面 / 输入输出说明 / 官方题解等 Markdown 富文本统一使用 `components/MarkdownView.vue` 渲染（markdown-it `html:false` + DOMPurify 白名单过滤，见 `docs/decisions/2026-08-23-problem-statement-markdown.md`）；禁止对用户可控内容直接 `v-html`。
- 页面级共享类（`.page-stack` / `.section-title` / `.form-hint` / `.result-box`）统一定义在 `assets/main.css`，各视图复用；scoped CSS 只写组件特有样式，不允许跨视图复制同一规则。

## 国际化（强制）

- 所有用户可见静态文案必须位于 `src/frontend/src/i18n/`，并使用 `t('key')` 或 `$t('key')`；禁止在 `.vue`/`.ts` 中硬编码自然语言。
- 覆盖范围包括：路由标题、导航、按钮、表单标签与 placeholder、表格列、状态字典、筛选项、空状态、弹窗、Toast、兜底错误、CSV 导出表头和可见提示。
- 每个新增或修改的 key 必须同时提供 `zh-CN` 和 `en-US` 内容；两种语言的 key 结构一致。
- 后端返回的业务错误消息可以按原样呈现；前端生成的兜底错误必须国际化。
- 用户切换语言后，菜单、页面标题、字典/标签和当前页面可见文案应即时更新，无需刷新（Naive 组件文案经 n-config-provider 的 locale 提供）。

## 代码组织

```text
src/frontend/
  eslint.config.js   # ESLint flat config（Vue essential + TS recommended）
  .prettierrc.json   # Prettier（格式化唯一权威；ESLint 关闭格式类规则）
  vite.config.ts     # Vite 配置 + Vitest test 块（jsdom 环境）
  src/
    api/            # 统一 HTTP 与领域 API，不放组件展示逻辑；错误分支须有 *.spec.ts 用例
    assets/         # 全局样式、布局层 CSS 变量
    components/     # 跨领域可复用展示组件
    constants/      # 展示字典（随 locale 动态翻译）
    i18n/           # locale、词典与语言工具
    layout/         # 应用壳：侧栏 / 顶栏 / 面包屑 / 用户区
    router/         # 路由表与守卫（meta 驱动菜单 / 标题 / 权限）
    settings/       # 布局尺寸与 Naive UI themeOverrides
    stores/         # 跨页面状态（user 会话、app 壳状态）
    types/          # 与 docs/contracts/ 对齐的共享类型，统一出口 @/types
    utils/          # 无 UI 副作用的工具函数；feedback.ts 为全局消息/确认 API
    views/          # 路由页面，管理页面状态和编排
```

- 页面组件可管理请求、筛选、弹窗和本页状态；纯展示组件通过 props/emits 工作。
- 通过 `api/` 调用后端，统一处理 `{ code, message, data }` 信封；组件不得直接拼接服务端基址。
- 组件样式优先使用 Naive UI；布局、间距和响应式使用 Tailwind 原子类。确需 scoped CSS 时只写该组件特有样式。
- 不在组件中硬编码环境 URL、密钥、Token 或权限绕过逻辑。
- 单元测试与被测文件同目录，命名 `*.spec.ts`（utils / constants / api 层必须覆盖）。

## 工具链与质量门禁

| 工具 | 配置 | 命令 |
| --- | --- | --- |
| ESLint | `eslint.config.js` | `npm run lint:check`（自动修复用 `npm run lint`） |
| Prettier | `.prettierrc.json` | `npm run format` |
| Vitest | `vite.config.ts` 的 `test` 块 | `npm test` |
| 类型检查 + 构建 | `tsconfig.json` | `npm run build` |

- 格式类规则统一交给 Prettier，ESLint 经 `@vue/eslint-config-prettier/skip-formatting` 关闭重叠规则，双工具不打架。
- 模板内联事件**禁止多条语句**（如 `@click="a = 1; load()"`）：Prettier 折行后会生成非法模板表达式，一律收敛为 script 内方法。
- `@typescript-eslint/no-explicit-any` 暂关闭（存量清理后开启）；下划线前缀表示有意保留的未用变量。

## 路由与导航规则

- 一级侧栏导航是业务区块入口；进入其子路由时，该一级菜单必须保持激活（前台按 matched[1] 区块定位，后台按 `/admin/<区块>` 前缀定位）。
- 单可见子路由的区块（如 题库→列表）在侧栏拍平为单项。
- **对象上下文页面**（创建题目、编辑、提交详情、评测结果）是所属区块的嵌套路由，标记 `meta.contextPage: true` 与 `meta.hidden: true`；它们通过面包屑和页内导航定位，归属工作台用 `breadcrumbParent` 声明（如 编辑题目 → 管理后台/题目管理）。公开落地页（如验题邀请 `/verify/:token`）与登录/注册同级，独立于应用壳布局。
- 路由标题、菜单标题必须设置 `meta.titleKey`，由 i18n 生成；`meta.title` 仅作兼容性后备。
- 浏览器标签标题格式为「页面标题 · 站点名」、favicon 取站点配置 `site.logo`（外链 URL；未配置回退 🐦 默认图标），随 `GET /site-config` 异步生效。
- 侧栏属于导航层，禁止直接读取 `meta.title` 展示；没有 `titleKey` 的路由不得进入导航目录。
- 菜单及路由继续按照 `meta.roles` 过滤，前端显示不是权限校验的替代品。

## 前端验收与验证

每次前端变更至少完成：

1. `npm run lint:check`（ESLint 静态检查；提交前可用 `npm run format` 统一 Prettier 格式）；
2. `npm run build`（类型检查与生产构建）；
3. `npm test`（Vitest 单元测试；新增 utils / api 层逻辑必须附带同目录 `*.spec.ts` 用例）；
4. 涉及界面/交互时，在中文与 English 下分别检查关键页面、亮暗主题、窄屏布局、loading/error/empty 状态；
5. 涉及路由/导航时，验证侧栏激活、子路由跳转、浏览器标题和权限过滤；
6. 涉及 i18n 时，扫描新增的用户可见文案，确认不存在未迁移的硬编码文本。
