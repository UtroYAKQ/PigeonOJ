# 前端设计规范

> 前端设计系统、布局、组件、i18n 与质量门禁约定。修改 `src/frontend/` 前必读；API、数据模型、权限仍须遵循 `docs/architecture.md` 与 `docs/contracts/`。

## 技术栈

Vue 3 · Vue Router · Pinia · Naive UI · Tailwind CSS v4（原子类辅助布局）· vue-i18n · Monaco Editor。图标源 `@element-plus/icons-vue`（独立 SVG 组件，在 `n-icon` 中渲染），`meta.icon` 名称见 `layout/icon.ts`。未经决策记录不得替换或新增同类框架。

## 设计系统

### 色板与令牌

- 主色橙 `#F4511E`（pressed `#D84315`）；info `#2080F0` / success `#18A058` / warning `#F0A020` / error `#D03050`；圆角 3px
- Naive UI 主题经 `settings/theme.ts` 的 `themeOverrides` 注入，**不使用** CSS 变量映射组件库主题
- 布局层 CSS 变量唯一来源：`assets/main.css` 的 `:root` + `html.dark`（`--app-primary / --app-content-bg / --app-card-bg / --app-chrome-bg / --app-border / --app-text / --app-text-secondary / --app-muted-bg`，及语义色 `--app-info / success / warning / error`）；组件只允许引用令牌，禁止硬编码色值
- 暗色模式：`html.dark` class 驱动（Tailwind `dark:` 变体、Monaco 主题同步），持久化 localStorage，登录后跟随用户偏好（stores/app + stores/user）

> 参考 [vue-fastapi-admin](https://github.com/mizhexiaoxiao/vue-fastapi-admin)。

### 应用壳

1. **侧边栏**：展开 220px / 收起 64px（图标态，tooltip 显示名称），白底右边框；Logo 主色块 + 主色标题（站点名 / Logo 来自 `GET /site-config`，未配置回退默认）；`n-menu accordion`，选中项左侧 4px 主色描边；窄屏 ≤991px 强制收起
2. **顶栏**：白底 60px 下边框；左侧折叠钮 + 面包屑（<667px 隐藏），右侧语言 / 明暗 / 头像菜单
3. **内容画布**：浅灰蓝 `--app-content-bg`；页面内容白底无边框 `n-card` 承载，间距 12–16px
4. **管理后台空间**：进入 `/admin` 后侧栏整体切换为管理菜单，底部「返回前台」；面向 staff（admin / tutor），tutor 仅见「题目管理」，admin 见全部
5. **面包屑**：只反映真实层级（`管理后台/用户管理`、`题库/题目管理/编辑`），首页与顶级区块平级不入

### 交互习惯

- 危险操作（删除、封禁、注销、提交）先确认再执行；确认弹窗用 `utils/feedback.ts` 的 `$dialog.warning`；需输入的（封禁原因、注销密码）用内联 `n-modal`
- 命令式反馈统一走 `utils/feedback.ts`（message / dialog，createDiscreteApi），组件内不再包 MessageProvider
- 配置多分类页面用横向 `n-tabs type="line"`
- **刷新按钮统一复用 `components/RefreshButton.vue`**（icon-only 圆形幽灵按钮，`loading` 传入加载态）：加载中图标自旋表达状态，禁止绑 naive `:loading`（图标被整体替换为转圈组件，产生尺寸跳变与视觉突兀）；查询进度由页面表格 / 内容区的 loading 遮罩承担；aria-label 与 @click 经 attrs 透传

### 表格工作台

- 筛选 / 搜索 / 导出放工具栏（允许换行）；表格 `n-data-table`（columns 数组 + render，列文案随 locale 翻译）；行内操作 `text` 按钮；分页底部分页器
- 复用 `components/PaginatedDataTable.vue` + `composables/usePagination.ts`（含空态垂直居中 + 底部分页条，页面不得手写同构样板）
- 外壳复用 `components/WorkbenchShell.vue`（page-fill 视口锁定 + 无边框卡片；支持 `title` / `header` / `header-extra` 插槽），页面不得手写 `.page-fill` + `n-card` 样板；表格区 `table-fill`，空态经 `table-fill-empty` 居中
- 字典层标签类型（`TagType`）渲染到 `n-tag` 时须经 `toNaiveTagType()` 映射（danger → error）

### 按钮与表单

- 每个操作区域最多一个主按钮；次要操作用 `secondary` / 默认；行内操作用 `text`
- 删除 / 封禁 / 注销用 `type="error"`，文案描述结果
- 表单 `label-placement="top"`；必填/格式/范围用控件规则；提交按钮显示 loading
- 统一覆盖 loading / error / empty / success 状态

### 「题面 + 编辑器」双栏工作台

复用 `components/problem/ProblemWorkbench.vue`：占满视口剩余高度，整页无滚动条、各栏独立滚动；比例持久化 localStorage；窄屏 <900px 上下堆叠；分隔条 `role="separator"` + 提示文案。工具行固定为「语言选择 + 我的提交 + 提交代码」，按钮只抛事件，行为由宿主注入。

### 可访问性

- 图标按钮必须有可见文字、`aria-label` 或 `n-tooltip`
- 不单一靠颜色传递状态，状态标签含文本
- 键盘可聚焦；弹窗焦点留在弹窗内

## Markdown 渲染

- 题面 / 背景 / 输入输出说明 / 官方题解用 `components/MarkdownView.vue` 渲染（markdown-it `html:false` + DOMPurify 白名单）；禁止对用户可控内容直接 `v-html`
- 编辑：`components/MarkdownEditor.vue`（md-editor-v3 封装，CodeMirror 编辑，工具栏「纯预览」切换，暗色/语言跟随全局）
- 插图：`POST /files/upload/image`（登录用户，≤5MB，JPG/PNG/WEBP/GIF），插入 `![](url)`，限宽 50%
- 数学公式：编辑器与展示侧均支持 KaTeX（`$...$` 行内 / `$$...$$` 块级）

## 国际化

- 所有用户可见静态文案位于 `src/frontend/src/i18n/`，使用 `t('key')` / `$t('key')`；禁止硬编码自然语言
- 覆盖范围：路由标题、导航、按钮、表单标签与 placeholder、表格列、状态字典、筛选项、空状态、弹窗、Toast、兜底错误、CSV 导出表头
- 每个 key 必须同时提供 `zh-CN` 与 `en-US`；切换语言后即时更新

## 共享组件

| 组件 | 用途 | 共用页面 |
| --- | --- | --- |
| `components/problem/ProblemWorkbench.vue` | 题面 + 编辑器双栏 | 题目详情 / 编辑向导 |
| `components/problem/ProblemMetaBar.vue` | 标题 + 限制 + 标签 | 题目详情 / 管理 |
| `components/problem/ProblemStatement.vue` | 描述 + 输入输出 + 样例 | 题目详情 / 管理 |
| `components/problem/ProblemSamples.vue` | 展示样例（各带复制） | 详情 / 邀请落地页 |
| `components/WizardShell.vue` | 页眉卡片（标题 + 步骤序号 + 动作） | 写题向导多步骤 |
| `components/StatusTag.vue` | 状态 → 标签颜色/文案 | 提交历史 / 结果页 |
| `components/EmailCodeInput.vue` | 验证码输入 + 60s 倒计时 | 注册 / 安全设置 |
| `components/PaginatedDataTable.vue` + `composables/usePagination.ts` | 分页列表 | 所有管理列表 |
| `components/WorkbenchShell.vue` | 视口锁定工作台外壳（page-fill 卡片 + 头部插槽） | 所有管理列表 |
| `components/RefreshButton.vue` | 刷新按钮（icon-only 圆形幽灵按钮，加载中图标自旋） | 列表 / 状态页 |
| `constants/languages.ts` | 判题语言选项 | 所有语言选择器 |

## 代码组织

```text
src/frontend/
  eslint.config.js       # ESLint flat config（Vue + TS）
  .prettierrc.json       # Prettier（格式化唯一权威）
  vite.config.ts         # Vite + Vitest
  src/
    api/                 # 统一 HTTP 与领域 API
    assets/              # 全局样式、布局层 CSS 变量
    components/          # 跨领域可复用展示组件
    constants/           # 展示字典
    i18n/                # 语言文件
    layout/              # 应用壳
    router/              # 路由 + 守卫（meta 驱动菜单 / 标题 / 权限）
    settings/            # 布局尺寸 + themeOverrides
    stores/              # 跨页面状态
    types/               # 与 contracts 对齐的共享类型
    utils/               # 无 UI 副作用工具
    views/               # 路由页面
```

- 页面组件管理请求、筛选、弹窗、本页状态；纯展示组件 props/emits 工作
- 通过 `api/` 调用后端，统一处理 `{ code, message, data }` 信封
- 样式优先 Naive UI；布局、间距、响应式用 Tailwind 原子类
- 不在组件中硬编码环境 URL、密钥、Token 或权限绕过逻辑
- 单元测试与被测文件同目录，命名 `*.spec.ts`

## 工具链与质量门禁

| 工具 | 命令 | 说明 |
| --- | --- | --- |
| ESLint（`eslint.config.js`） | `npm run lint:check` / `npm run lint` | 静态检查 / 自动修复 |
| Prettier（`.prettierrc.json`） | `npm run format` | 一键格式化 |
| Vitest | `npm test` | 单元测试（jsdom） |
| 类型检查 + 构建 | `npm run build` | `vue-tsc -b` + vite build |

- 格式类规则统一交给 Prettier，ESLint 关闭重叠规则
- 模板内联事件禁止多条语句（Prettier 折行生成非法表达式）
- `@typescript-eslint/no-explicit-any` 暂关闭

## 路由与导航

- 一级侧栏是业务区块入口；子路由激活时一级菜单保持激活
- 对象上下文页面（创建题目、编辑、提交详情、评测结果）标记 `meta.contextPage: true` + `meta.hidden: true`；归属工作台用 `breadcrumbParent` 声明
- 路由标题 / 菜单标题设 `meta.titleKey`，由 i18n 生成；无 `titleKey` 的路由不得进导航目录
- 浏览器标签「页面标题 · 站点名」，favicon 取 `site.logo`

### 路由上下文隔离（契约级规范）

> 设计术语对齐：本节即 **限界上下文**（Bounded Context，DDD）在前端路由层的应用——
> 同一资源在不同业务上下文中拥有独立的交互闭环；规则 2、3 落实 **迪米特法则**
> （Law of Demeter，只与直接上下文通信）；规则 4 是 **模块统一入口**
> （Facade 门面模式）+ **REST 嵌套资源**（归属关系写入 URL，入口即校验）。

同一资源页面被多个业务上下文复用（题目详情 / 评测结果 / 预览 × 题库、题单、管理后台）时，
每个上下文拥有**独立路由实例**，上下文内的所有导航与交互必须封闭在本上下文路由内，
**禁止把用户带离当前业务上下文**。实例：题库 `/problems/:id`、题单
`/problem-sets/:setId/problems/:problemId`、管理后台 `/admin/problem-sets/:id/problems/:pid/preview`。

规则：

1. **上下文路由独立**：每个上下文为自己的 URL 前缀下声明路由（页面组件可复用），
   上下文专属路由声明在所属业务区块的 children 内，紧随其列表 / 详情路由之后。
2. **禁止跨上下文跳转**：进入下一层、返回上一层、提交后跳转都必须落在本上下文路由内；
   如题单内交题、查看评测结果不得跳 `/problems/:id`；管理端点击资源不得进入作答 / 写作页面。
3. **组件复用取参**：复用组件按「上下文参数优先」取参
   （如 `route.params.problemId ?? route.params.id`），内部链接基于上下文动态构造
   （如评测结果基路径 `submissionsBase`），不得硬编码单一前缀。
4. **配套后端上下文端点（模块统一入口，Facade）**：上下文内对资源的读 / 写调用本上下文模块的
   专属端点，不跨模块直调（读如题单内题目详情 `GET /problem-sets/{id}/problems/{pid}`，
   写如题单交题 `POST .../submissions`）；端点在入口校验资源归属关系
   （题单可见 + 题目属于该题单），装配与业务链路复用统一实现，保证多入口行为一致。
5. **面包屑真实层级**：面包屑按当前上下文展示完整父链
   （题单 / 题单详情 / 题目详情 / 评测结果；管理后台 / 题单管理 / 题单详情），
   `breadcrumbParent` 支持函数动态解析路径与数组多级父链，中间级必须可点击回跳。
6. **管理端只读隔离**：管理后台的资源浏览页点击资源仅打开**只读预览**
   （如题单管理内的题目预览），禁止跳转前台交互页面；管理操作收敛在 `/admin`，前台只留浏览。
7. **新增上下文时同步契约**：引入新的上下文路由（或新的资源页面复用）必须同步更新
   `docs/contracts/` 对应模块契约（端点表、关键流程、前端页面说明），跨模块公共语义落在本文件。

> 完整实例参见 `docs/contracts/problem-sets.md`「关键流程 / 验收条件」（题库 / 题单 / 管理后台
> 三上下文的路由隔离、专属交题端点与只读预览约束）。

## 前端验收

每次前端变更至少完成：

1. `npm run lint:check`（+ `npm run format`）
2. `npm run build`（类型检查 + 构建）
3. `npm test`（Vitest；utils / api 层须有 `*.spec.ts`）
4. 涉及界面时，中英文 + 亮暗主题 + 窄屏 + loading/error/empty 双语言检查
5. 涉及路由时，验证侧栏激活、子跳转、标题、权限过滤
6. 涉及 i18n 时，扫描新增文案确认无硬编码
