# 前端设计规范

> 设计系统、布局、组件、i18n 与质量门禁。改 `src/frontend-next/` 前必读。
> API / 权限 / 数据模型见 `contracts.md` 与 `architecture.md` §5。
> `src/frontend/` 为旧版（naive-ui）实现，仅作迁移参考；行为、路由与 API 契约以本文件与新工程为准。

## 1. 技术栈

Vue 3 · Vue Router 4 · Pinia · **shadcn-vue**（reka-ui 无头组件）· Tailwind CSS v4 · vue-i18n · Monaco Editor · vue-sonner（Toast）· lucide 图标（`@lucide/vue`）。

未经决策记录不得替换或新增同类框架。shadcn-vue 通过 `components.json`（style `new-york`）管理，`components/ui/` 原子组件统一从 `@/lib/utils` 引入 `cn`；新增组件用 `npx shadcn-vue add <name>` 增量添加。

## 2. 设计系统

### 2.1 外观基调

- 中性 shadcn 基调：浅色 `#ffffff / #0d0d0d`，深色 `#212121 / #ececec`；1px `--border` 描边
- **卡片统一 `rounded-md border bg-card`、无阴影**；浮层（Dialog / Popover / Dropdown）保留 shadcn 默认阴影以示层级
- 列表表头统一 `bg-surface`（`--surface` 令牌，与 Markdown 表头同一表面层），高度统一 40px
- 外观以 shadcn 默认为准，不逐组件自定义变体；深色下的可见性问题优先通过令牌解决

### 2.2 色板与令牌

- `--surface`（浅 `#f7f7f8` / 深 `#2f2f2f`）用于内嵌表面：Markdown 表头、列表表头、次级面板、占位块；深色下与卡片同色，避免表头出现比容器更黑的条带
- 品牌橙 `--brand`（浅 `#d9480f` / 深 `#f08a5d`）**只用于强调**：链接 hover、选中态点缀、Markdown 链接；主按钮为近黑中性色；Logo 保持透明底原色显示
- 语义色 success / warning / info / destructive 经 `components/common/tone.ts` 统一映射，由 `StatusTag`、`ToneBadge` 消费；**禁止页面各自硬编码**
- 令牌唯一来源：`src/assets/main.css` 的 `:root` 与 `.dark`。组件只允许引用 token，禁止硬编码色值
- 字体：Geist + Noto Sans SC（正文 / 标题）、Geist Mono + JetBrains Mono（代码）；字号 13–15px 为主，表格与工具条 12–13.5px
- 圆角取 `main.css` 的 `--radius-*`：sm 4 / md 6 / lg 8 / xl 10 / 2xl 12 / 3xl 16 / 4xl 20px。卡片与按钮 / 输入框用 `rounded-md`；除头像 / 徽标等 pill 外不要写死 `rounded-full` 或任意圆角值
- 暗色模式：`html.dark` class 驱动（Tailwind `dark:` 变体 + Monaco 主题同步）；首屏由 `index.html` 内联脚本读 localStorage 提前置 class 避免闪烁；登录后跟随用户偏好
- 深色控件可见性：`--border` 0.16 / `--input` 0.24 / `--accent` #3a3a3a，保证分页下拉边框与 hover 底色可辨（不改组件变体）

### 2.3 应用壳

1. **侧栏**：展开 256px / 收起 0；`bg-sidebar` 浅灰面，品牌块（站点 Logo 或 Bird 图标，透底无底色块）+ 站点名 + 副标题；导航项 36px 高、圆角 6px，选中项白底 + 边框；前台导航为 首页 / 题库 / 题单 / 比赛 / 团队 / 组织 / 代码广场
2. **后台空间**：`/admin/*` 时侧栏切换为管理菜单（内容 / 社区 / 数据 / 系统 四组），底部「返回前台」；管理入口与区块仅 `admin`
3. **顶栏**：56px 下边框；左侧侧栏开关 + 面包屑（<640px 隐藏）、命令面板入口（Ctrl/⌘+K），右侧语言 / 明暗切换；账户菜单统一收在侧栏底部用户区（个人资料 / 管理后台 / 退出）
4. **内容画布**：列表页桌面（≥`lg`）用 `WorkbenchShell` 视口锁定（工具栏 + 列表内部滚动）；窄屏自然高度整页滚动。列表壳最小高度兜底：`ColumnLineList` / `PaginatedCardGrid` 320px、`LineList` 240px；团队 / 组织详情下半区最小 420px。内容页用 `PageShell`（最大 1360px 居中、自然滚动）
5. **面包屑**：只反映真实层级；`router/crumbs.ts` 为唯一解析来源
6. **命令面板**：可搜索全部前台 / 后台菜单与账户页；`↑↓` 选择、`Enter` 打开、`Esc` 关闭

### 2.4 响应式

- 断点按 Tailwind：`sm 640` / `md 768` / `lg 1024` / `xl 1280` / `2xl 1536`；`SplitPane` 内部用 `900px` 判断上下堆叠。新增布局优先复用，不另造值
- <1024：常驻侧栏隐藏，导航改 `ui/sheet` 左侧抽屉（284px / max 86vw）；<640：顶栏面包屑隐藏，搜索入口收为图标按钮
- 表格窄屏策略：`ColumnLineList` 未显式传 `minWidth` 时默认 `min-width: 640px`，**横向滚动展示全部列**，不把列压到几像素；`Pager` 在 ≤640px 收起页码窗口（`sibling-count=0`）
- 列表工具条：`SearchFilterBar` 搜索框窄屏 `w-full`，≥640 才用传入的 `searchWidth`；整体允许换行
- 团队 / 组织详情：摘要卡文本列至少 200px，操作按钮组窄屏独占一行；功能导航窄屏横排可横向滚动（`scrollbar-none`），按钮高 40px
- 主区滚动容器 `overscroll-contain`，避免移动端回弹；触控目标不低于 32px，导航 / 主操作按钮优先 40px

### 2.5 图片

站内 `/api/v1/files/` 地址统一经 `utils/image.ts` 的 `siteImageUrl` / `avatarImageUrl` 改写为 `?w=` 缩略档（96/192/384/640/960/1280，后端按档生成 WebP）：头像按 2x 取档、题面 / 评论插图 960、轮播桌面 1280 / 窄屏 960。Markdown 图片与列表图统一 `loading="lazy" decoding="async"`；轮播窄屏只预取当前 + 下一张。**外链原样不改写。**

## 3. 交互习惯

### 3.1 列表与工作台

- 页面结构：`WorkbenchShell` → `#toolbar` 放 `SearchFilterBar`，筛选条件（状态 / 类型）统一用 `ui/select` 下拉并与搜索框同行，**不用 Tabs 做筛选**（Tabs 仅用于详情页内容分区）→ `LineList` / `PaginatedTable` / `PaginatedCardGrid`
- 列表形态选择：**列驱动列表**（管理后台列表、提交、日志、明细）用 `ColumnLineList` / `PaginatedTable`（基于 `ui/table`）；**自由插槽的「一行一条」**用 `LineList` 无框横线壳；**网格浏览型实体**（团队 / 组织 / 比赛 / 代码广场）用 `PaginatedCardGrid`
- 列定义 `AppTableColumn<T>`（`key/title/width/align/cell`）；**禁止各页手写原生 `<table>` 或 `divide-y` 列表壳**
- 搜索统一**手动触发**：输入只同步关键词，点「查询」或回车才发起；清空（X）立即按空关键词重查
- 分页：`PaginatedTable` / `PaginatedCardGrid` 内置 `Pager`；页面只维护 `usePagination()` 的 page / pageSize / total，慢响应用 `beginLoad/isCurrent` 守卫
- 批量操作：`PaginatedTable` 支持可选 `selectable / rowKey / selectedKeys`（跨页保留勾选）
- 空态、加载、错误三态必须覆盖。列表空态容器统一 `.list-empty`（`main.css`：`flex:1` 撑满 + 双向居中），**禁止各页另写 `grid place-items-center`**
- 前台可见性展示：不单独占「可见性」列；题库「我的题目」与团队题目列表仅对 `private` / `admin_visible` 在名称旁打小 tag，组织团队列表仅对 `private` 打 tag；**后台管理列表仍保留独立可见性列**
- 题库列表「标签」列用 `ProblemTagBadge`（按标签 `color` 取描边 / 文字色），不拼成逗号 / 斜杠纯文本；标签列可在工具条勾选显隐，偏好写 `pigeonoj.problems.showTags`
- 卡片列表：`EntityCard` 作整卡可点击外壳（支持 Enter / Space 与可见焦点环）。实体卡沿用简约范式：单行头部（头像 + 名称 + 角色 / 状态点标）、描述最多两行截断、底部两行（元信息行 + `border-t` 分隔的时间行）；**不放「查看 / 申请加入」行动文案、右箭头或重复徽标**
- 比赛 / 代码分享卡片保持极简：头像 / 图标 + 标题 + 两行简介 + 纯文本元信息；只在确有必要时保留一个状态徽标；hover 只轻微描边

### 3.2 反馈与确认

- 危险操作（删除、封禁、注销、退出团队、提交）先确认再执行；统一走 `utils/feedback.ts` 的 `confirmDialog`（Promise，底层 `ui/alert-dialog`）
- 命令式提示统一 `utils/feedback.ts`（`ui/sonner` 的 Toaster 承载）：`message.success/error/warning/info/loading`；**组件内不重复挂 Provider**
- 图标按钮必须有 `aria-label` 或 `TooltipHint`；不单靠颜色传递状态
- 刷新按钮统一复用 `RefreshButton.vue`（icon-only 幽灵按钮，loading 自旋）；调用方直接 `@click="load"`

### 3.3 表单与按钮

- 每个操作区域最多一个主按钮；次要操作用 `outline` / `ghost`；危险操作用 `destructive`
- 工具条按钮统一 `size="toolbar"`（36px，与输入框 / 选择器同高）；对话框内操作保持 `size="sm"`，不用 `class="h-9"` 临时抬高
- 表单 `Label` 置顶；必填 / 范围用控件属性与提交前校验；提交按钮 loading 用 `Loader2` 自旋 + 禁用
- 表单内编辑器工具栏按钮（如 `MarkdownEditor` 的加粗 / 预览）必须显式 `type="button"`，避免默认 `submit` 误触发保存
- 弹窗用 `ui/dialog`（受控 `v-model:open`），必须有 `DialogTitle`（可 `sr-only`）；输入型确认（封禁原因、密码）在弹窗内完成
- 列表工具条的筛选开关统一用 `FilterCheckbox`（整行可点击），不用 `Switch`；配置编辑等非列表场景的布尔开关仍可用 `Switch`
- 详情页按任务拆 Tabs（共享 `ui/tabs`），禁止自造按钮组
- **创建 / 编辑表单页统一无框版式**：标题 + `WizardSteps` 步骤条（向导页）+ 细分隔线分区 + 字段下方提示，底部左对齐操作按钮。不再用卡片外壳（`WizardShell` 已移除）。适用：出题向导三页、比赛创建向导两页、题单新建 / 编辑、团队创建比赛 / 题单 / 引用页
- **设置页**（组织 / 团队设置、系统配置、首页配置）仿 shadcn 设置页：标题 + 说明 + 细分隔线 + 无边框表单（`space-y-8`，字段下方说明，左对齐提交按钮），**不再用嵌套 `rounded-xl border bg-card` 卡片包裹**
- 团队 / 组织详情用「顶部摘要卡 + 下方功能卡」上下布局（操作与刷新按钮放摘要卡内），下方卡内左侧 `Button variant="ghost"` 竖排功能导航（窄屏横排置顶）、右侧内容区（各面板 `v-show` 懒挂载），不用横向 `TabsList`；两卡间 `mt-4`
- 选择成员 / 初始管理员统一用 `UserEmailPicker`：输入**完整邮箱**手动查询（按钮 / 回车），结果行点击添加、已选标签可移除；**不回退到手输 UUID**

### 3.4 代码展示与编辑器

- 只读代码统一 `ui/code-block`（`CodeBlockView.vue` 封装：语言标签 + Shiki 高亮 + 行号 + 复制）；Markdown 里的 fenced code 由 `MarkdownView` 渲染后补高亮。语言映射 `cpp17 → cpp`、`python3.12 → python`、`java21 → java`，新增语言须在 `ui/code-block/highlighter.ts` 注册
- 编辑器字号 / 字体偏好来自用户资料（`editor_font_size` / `editor_font_family`），`CodeEditor` 统一消费，保存后即时生效
- `CodeEditor` 自身不设最小高度（`min-h-0`），由父容器给定；需要时在父级 `min-h-*` 声明，避免嵌套最小高度叠加导致相邻面板溢出
- Monaco 字体偏好变更必须按「显式 `document.fonts.load` 等字体 → `remeasureFonts()` 清度量缓存 → `updateOptions`」顺序应用，否则字符宽度误差会累积成光标 / 文本偏移；容器不设 `padding`、隐藏横向滚动条；keep-alive 返回与容器尺寸变化都要 `layout()`；关闭 `minimap` 与 `stickyScroll`（顶部粘性代码块），编辑区只保留代码本体

### 3.5 「题面 + 编辑器」双栏工作台

- `SplitPane`：桌面左右独立滚动、分隔条可拖拽且比例持久化（双击复位）；<900px 自动上下堆叠
- `ProblemWorkbench`：左题面（`ProblemMetaBar` + `ProblemStatement`），右编辑器 + 自测控制台
  - **右栏高度固定**：窄屏 `h-[min(70lvh,640px)]`（`lvh` 取大视口，软键盘弹出不改变高度）、≥900px `h-full`；编辑器宿主 `min-h-0 flex-1`，Monaco 高度链在固定区域内闭合。窄屏**不要**用自然高度，否则拖控制台会让页面越拉越长
  - 编辑器宿主窄屏用 `h-[clamp(220px,42vh,300px)]` 给 Monaco 确定高度；只写 `h-full` 时上层为 auto，Monaco 的 `height:100%` 会塌成 0（只剩边框）
  - 工具行：「语言」靠左、「我的提交 / 题解」靠右；「自测运行 / 提交」放进下方控制台标题行
  - 自测控制台常驻编辑器下方：顶部中央 64×14 凹口把手（单击开合、按住拖拽调高，位移 <3px 视为单击；方向键 / Home 微调与复位），默认展开 520px、拖拽下限 140px（展开时沿用上次高度，含手动压缩后的较小值，不强制抬到固定下限）；上限为「右栏可用高度 − 工具栏」，`allowCover=true` 时可覆盖整个编辑区；收起态只留约 47px 控制条；点当前已展开的 tab 会收起面板；控制条内 tab 后紧接「自测运行」，右侧「提交代码」**必须始终可见**（控制条允许换行）；高度按 px 持久化到 `pigeonoj.problems.consoleHeight.v2`，拖拽 / 键盘 / 展开 / 切 tab / 自测 / 窗口自适应引起的变化都要写入，保证再次打开沿用同一高度；控制台输入区聚焦（移动端软键盘）期间冻结高度
  - Monaco 在 ≤640px 自动 `wordWrap: 'on'`
- 提交历史经 `MySubmissionsDialog` 懒加载分页（`sm:max-w-[760px]`、高 `min(72vh,520px)`），行点击进入上下文内评测结果页
- 题目预览与评测结果同为 `PageShell` 无框分区：标题 + 灰色说明 + 细分隔线，刷新 / 返回放页头，统计用纯文本，代码与测试点各自成段

### 3.6 可访问性

- 图标按钮必须有可见文字、`aria-label` 或 Tooltip；弹窗焦点留在弹窗内
- 状态标签含文本；键盘可聚焦；命令面板 / 弹窗支持 `Esc` 关闭

## 4. Markdown

- 渲染统一 `MarkdownView`（markdown-it `html:false` + DOMPurify 白名单 + KaTeX）
- 编辑统一 `MarkdownEditor`（textarea + 工具栏 + 写 / 预览切换 + 粘贴 / 选择图片上传）；存储仍为纯 Markdown
- 评论输入用 Tiptap 所见即所得（`@tiptap/vue-3` + `tiptap-markdown`）：图片内联在文字流，提交仍输出 Markdown；展示统一 `renderCommentMarkdown`（图片仅允许站内 `/api/v1/files/`，外部图床退回 alt）
- 插图：`POST /files/upload/image`（登录用户，≤5MB）；题面展示限宽 50%
- **禁止对用户可控内容直接 `v-html`**（仅 `MarkdownView` / `renderCommentMarkdown` 内部经白名单渲染）

## 5. 国际化

- 所有用户可见静态文案位于 `src/i18n/locales/`，使用 `t('key')`；**禁止硬编码自然语言**
- 每个 key 必须同时提供 `zh-CN` 与 `en-US`；`src/i18n/keys.spec.ts` 扫描模板 / 路由中的静态 key，缺失即测试失败
- 覆盖范围：路由标题、导航、按钮、表单标签与 placeholder、表格列、状态字典、筛选项、空状态、弹窗、Toast、兜底错误、CSV 导出表头

## 6. 路由与导航

- 一级侧栏是业务区块入口；子路由激活时一级菜单保持激活
- 对象上下文页面（创建题目、编辑、提交详情、评测结果）标记 `meta.contextPage: true` + `meta.hidden: true`；归属工作台用 `breadcrumbParent` 声明
- 路由标题 / 菜单标题设 `meta.titleKey`，由 i18n 生成；无 `titleKey` 的路由不得进导航目录
- 浏览器标签「页面标题 · 站点名」；`public/` 根目录提供 `favicon.ico`、`favicon.png`、`apple-touch-icon.png`，并在 `index.html` 用绝对路径声明，后台配置 `site.logo` 时再动态覆盖
- `nginx.conf` 对这三个图标路径做精确匹配与短缓存，缺失文件直接 404，不能回退到 `index.html`；`.ico` → `image/x-icon`

### 6.1 页面实例缓存

`AppLayout.vue` 对 `router-view` 采用插槽分流：`meta.keepAlive: true` 的页面进 `<KeepAlive>`（key 为 `route.fullPath`），从上下文页返回时保留筛选、页码与已加载数据；`:max=8` LRU 兜底；缓存 key 绑定当前登录用户 id，登出 / 换号后整体作废。滚动容器是 `main`，每次导航重置到顶部。

- **缓存**：各列表 / 工作台（题库、题单、比赛、团队、组织、代码广场、管理后台列表与在线用户）、评测结果页
- **不缓存**：所有详情页、编辑页、上下文写题页、题目预览、邀请页、个人资料 / 安全设置
- 评测结果页轮询必须在 `onDeactivated` 暂停、`onActivated` 恢复；在线用户列表同理
- 写题代码不依赖页面缓存：按「用户 + 题目 + 语言」经 `useCodeDraft` 持久化到 localStorage
- 新增页面默认不缓存，仅列表 / 工作台可声明 `meta.keepAlive`

### 6.2 路由上下文隔离（契约级）

同一资源被多个上下文复用时（题目详情 / 评测结果 / 预览 × 题库、题单、比赛、团队），每个上下文拥有**独立路由实例**，上下文内所有导航与交互必须封闭在本上下文内，**禁止把用户带离当前业务上下文**。

实例：题库 `/problems/:id`、题单 `/problem-sets/:setId/problems/:problemId`、比赛 `/contests/:cid/problems/:problemId`、团队 `/teams/:teamId/problems/:problemId`、团队题单 `/teams/:teamId/sets/:setId/problems/:pid`、团队比赛 `/teams/:teamId/contests/:cid/*`、管理后台 `/admin/problem-sets/:id/problems/:pid/preview`。

1. **上下文路由独立**：每个上下文在自己的 URL 前缀下声明路由（页面组件可复用），紧随其列表 / 详情路由之后
2. **禁止跨上下文跳转**：进入下一层、返回上一层、提交后跳转都必须落在本上下文内
3. **组件复用取参**：按「上下文参数优先」取参（如 `route.params.problemId ?? route.params.id`），内部链接基于上下文动态构造（如评测结果基路径 `submissionsBase`）
4. **配套后端上下文端点**：上下文内读写调用本上下文的专属端点，不跨模块直调（见 `contracts.md` §3.4）
5. **面包屑真实层级**：`breadcrumbParent` 支持函数动态解析路径与数组多级父链，中间级必须可点击回跳
6. **管理端只读隔离**：管理后台浏览页点击资源仅打开只读预览，管理操作收敛在 `/admin`

## 7. 组织与社区

- **组织中心**：入口固定在侧栏「组织」；`/orgs/mine` 列表 + `/orgs/:orgId` 详情（成员 / 组织团队 / 组织题库 / 设置）。组织题目路由固定 `/orgs/:orgId/problems/...`，读题 / 交题 / 自测全留在组织上下文
- **团队创建**：唯一入口为组织详情「创建团队」
- **社区**：题解页随题目上下文挂载（各上下文各自的 `/solutions/*` 路由），官方题解收口题解页 Tab；题解分享列表用 `LineList`（作者头像 + 标题 + 摘要 + 作者 / 日期 + 评论数，行间横线，非表格）；代码广场 `/codes` 列表 / 分享 / 详情，编辑 `/codes/:id/edit` 为详情下级路由；评论与举报统一 `CommentThread.vue` / `ReportDialog.vue`
- **管理治理**：`/admin/orgs`、`/admin/solutions`、`/admin/codes` 分别负责组织、题解、代码分享；题解预览弹窗内可直接治理评论

## 8. 共享组件

| 组件 | 用途 |
| --- | --- |
| `BaseAvatar` | 头像 / Logo：空值或加载失败回退默认图（user/team/contest）；团队 / 比赛 Logo 固定浅色底 `#f4f4f5`，不随主题改色 |
| `LineList` | 自由插槽无框横线列表壳：表头 / 分隔线 / 骨架 / `.list-empty` 空态 / 可选分页，支持 `#item` |
| `ColumnLineList` + `table-types.ts` | 列驱动 shadcn 表格（由 `AppTableColumn` 生成表头 / 行 / 勾选） |
| `PaginatedTable` | `ColumnLineList` + 分页开关 |
| `PaginatedCardGrid` + `EntityCard` | 卡片列表壳（响应式网格 / 骨架 / 空态 / 分页）与整卡可点击外壳 |
| `Pager` | 分页条（页码窗口 + 总数 + 可选每页条数） |
| `EmptyState` / `ErrorState` | 空态 / 加载失败态（可带重试） |
| `InlineNotice` | 语义提示条（info / success / warning / danger / neutral） |
| `DateTimeField` | 统一 `datetime-local` 输入（时间戳模型 + 清空） |
| `SearchFilterBar` | 搜索框 + 筛选插槽 + 「查询」+ 右侧动作区 |
| `RefreshButton` / `FilterCheckbox` | 刷新按钮 / 列表工具条勾选筛选 |
| `WorkbenchShell` / `PageShell` | 视口锁定列表壳 / 自然滚动内容壳 |
| `StatusTag` / `ToneBadge` | 提交状态 / 通用语义徽标（取自 `tone.ts`） |
| `MarkdownView` / `MarkdownEditor` | Markdown 渲染 / 编辑 |
| `CodeEditor` / `SplitPane` | Monaco 编辑器 / 可拖拽双栏 |
| `EmailCodeInput` / `UserEmailPicker` | 邮箱验证码输入 / 邮箱精确查询选人 |
| `components/problem/*` | 题目元信息、题面、样例、工作台、提交历史、标签选择、测试点导入、SPJ 编辑 |
| `components/submission/SubmissionResult.vue` | 评测结果页统一展示（统计 / 代码 / 测试点） |
| `components/problemsets/ProblemPicker.vue` | 题库选择弹窗 |
| `components/contests/*`、`components/teams/*` | 比赛 / 团队领域组件 |
| `components/community/CommentThread.vue`、`ReportDialog.vue` | 评论与举报 |
| `layout/*` | 应用壳、侧栏、顶栏、命令面板、面包屑、语言 / 主题 / 用户菜单 |

## 9. 代码组织

```text
src/frontend-next/
  eslint.config.js       # ESLint flat config（Vue + TS）
  .prettierrc.json       # Prettier（格式化唯一权威）
  vite.config.ts         # Vite + Vitest
  src/
    api/                 # 统一 HTTP 与领域 API
    assets/              # 设计令牌、Monaco 覆盖样式、默认头像
    components/
      common/ ui/        # 通用展示 / 工作台组件；shadcn-vue 原子组件
      problem/ submission/ problemsets/ contests/ teams/  # 领域组件
    composables/         # 分页 / 防抖草稿 / 自测 / 轮询
    constants/ i18n/ layout/ monaco/ router/ stores/ types/ utils/
    views/               # 路由页面（按领域分目录；大页拆 components/ 子组件）
```

- 页面组件管理请求、筛选、弹窗、本页状态；展示组件用 props / emits / 插槽
- 单文件目标 <350 行；大详情页按任务拆 Tabs 子组件，禁止复制粘贴整段模板
- 通过 `api/` 调用后端，统一处理 `{ code, message, data }` 信封
- 样式优先 Tailwind 原子类 + 设计令牌；组件内复杂样式才写 scoped CSS
- 不在组件中硬编码环境 URL、密钥、Token 或权限绕过逻辑

## 10. 工具链与验收

| 工具 | 命令 | 说明 |
| --- | --- | --- |
| ESLint | `npm run lint:check` / `npm run lint` | 静态检查 / 自动修复 |
| Prettier | `npm run format` | 一键格式化 |
| Vitest | `npm test` | 单元测试（jsdom；含 i18n 静态 key 完整性） |
| 类型检查 + 构建 | `npm run build` | `vue-tsc -b` + `vite build` |

每次前端变更至少完成：

1. `npm run lint:check`（+ `npm run format`）
2. `npm run build`（类型检查 + 构建）
3. `npm test`
4. 涉及界面时：中英文 + 亮暗主题 + 窄屏 + loading/error/empty 检查
5. 涉及路由时：验证侧栏激活、子跳转、标题、权限过滤、上下文不外跳
6. 涉及 i18n 时：确认无硬编码文案（`keys.spec.ts` 必须通过）

> 模板内联事件禁止多条语句（Prettier 折行会生成非法表达式），多语句逻辑写方法。`@typescript-eslint/no-explicit-any` 暂关闭。
