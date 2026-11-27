# 前端设计规范

> 前端设计系统、布局、组件、i18n 与质量门禁约定。修改 `src/frontend-next/` 前必读；API、数据模型、权限仍须遵循 `docs/architecture.md` 与 `docs/contracts/`。
> `src/frontend/` 为旧版（naive-ui）实现，仅作迁移参考；行为、路由与 API 契约以本文件与新工程为准。

## 技术栈

Vue 3 · Vue Router 4 · Pinia · shadcn-vue（reka-ui 无头组件）· Tailwind CSS v4 · vue-i18n · Monaco Editor · vue-sonner（Toast）· lucide 图标（`@lucide/vue`）。未经决策记录不得替换或新增同类框架。shadcn-vue 通过 `components.json`（style `new-york`）管理，`components/ui/` 原子组件统一从 `@/lib/utils` 引入 `cn`，新增组件用 `npx shadcn-vue add <name>` 增量添加。

## 设计系统

### shadcn-vue 组件化（2026-11 改造）

- 项目通过 `components.json`（style `new-york`）接入 shadcn-vue，`components/ui/` 原子组件统一从 `@/lib/utils` 的 `cn` 取值；新增组件用 `npx shadcn-vue add <name>`
- 已补齐并按 shadcn 默认外观落地的组件：`Card`（卡片）、`Table`（表格）、`Skeleton`（骨架）、`Checkbox` / `RadioGroup`（勾选 / 单选）、`Avatar`（头像）、`Pagination`（分页）、`Breadcrumb`（面包屑）、`Command`（命令面板）、`AlertDialog`、`Collapsible`、`ScrollArea`、`Popover`、`Sonner` 等
- 共享组件已切换底层实现（对外 props / emits 不变）：`BaseAvatar`→`Avatar`、`FilterCheckbox`→`Checkbox`、`ColumnLineList` / `PaginatedTable`→`Table`、`LineList` / `PaginatedCardGrid` 骨架→`Skeleton`、`EntityCard`→`Card`、`Pager`→`Pagination`、`CrumbsBar`→`Breadcrumb`、`CommandPalette`→`Command`、`ConfirmDialogHost`→`AlertDialog`、`App.vue` Toaster→`Sonner`、`CollapsibleEditor`→`Collapsible`、角色 / 举报处理单选→`RadioGroup`、`ContestCountdown` 时间详情→`Popover`、侧栏导航滚动→`ScrollArea`
- 外观以 shadcn 默认为准：卡片统一 `rounded-md border bg-card`、**无阴影**（对齐旧 UI 的简约观感，`Card.vue` 已去掉 `shadow`），表格表头 / 行分隔线 / hover 采用 `ui/table` 默认样式，浮层 / 分页 / 面包屑采用组件库默认样式。浮层（Dialog / Popover / Dropdown）保留阴影以示层级；仅自由插槽的 `LineList` 行列表保留无框横线结构
- 列表表头统一 `bg-surface`（`--surface` 令牌，与 Markdown 表头同一表面层），不随所在卡片 / 弹窗背景漂移；表头高度统一 40px（`ColumnLineList` 用 `TableHead` 的 `h-10`，`LineList` 的 `#header` 内容用 `min-h-10`）

### 色板与令牌

- 中性 shadcn 基调：浅色 `#ffffff / #0d0d0d`，深色 `#212121 / #ececec`；1px `--border` 描边；卡片保持无阴影的平面感，浮层（Dialog / Popover / Dropdown）保留 shadcn 默认阴影
- `--surface`（浅色 `#f7f7f8` / 深色 `#2f2f2f`）用于内嵌表面：Markdown 表头、列表表头、次级面板与占位块；深色下与卡片 / 浮层同色，避免表头出现比容器更黑的条带
- 品牌橙 `--brand`（浅色 `#d9480f` / 深色 `#f08a5d`）只用于强调：链接 hover、选中态点缀、Markdown 链接；主按钮为近黑中性色；Logo 保持透明底、原色显示，不加品牌色块或描边遮盖
- 语义色：success 绿 / warning 琥珀 / info 蓝 / destructive 红，经 `components/common/tone.ts` 统一映射，由 `StatusTag`、`ToneBadge` 消费；禁止页面各自硬编码
- 令牌唯一来源：`src/frontend-next/src/assets/main.css` 的 `:root` 与 `.dark`（含 shadcn token）；组件只允许引用 token，禁止硬编码色值，也不再保留 `--app-*` 旧别名
- 字体：Geist + Noto Sans SC（正文/标题）、Geist Mono + JetBrains Mono（代码）；字号以 13–15px 为主，表格与工具条使用 12–13.5px
- 圆角统一取 `main.css` 的 `--radius-*`：sm 4 / md 6 / lg 8 / xl 10 / 2xl 12 / 3xl 16 / 4xl 20px（整体偏平），卡片用 `rounded-md`（6px、无阴影，对齐旧 UI）、按钮/输入框用 `rounded-md`；除头像 / 徽标等 pill 外不要写死 `rounded-full` 或任意圆角值
- 暗色模式：`html.dark` class 驱动（Tailwind `dark:` 变体、Monaco 主题同步），首屏由 `index.html` 内联脚本读取 localStorage 提前置 class，避免闪烁；登录后跟随用户偏好
- 深色控件可见性：分页保持 shadcn 原生变体（`PaginationItem` 非激活 `ghost`、激活 `outline`；`PaginationPrevious/Next` 用 `ghost`），不修改组件变体；通过深色令牌解决可见性——`--border` 0.16 / `--input` 0.24 / `--accent` #3a3a3a，保证分页下拉边框与 hover 底色可辨

### 应用壳

1. **侧栏**：展开 256px / 收起 0；`bg-sidebar` 浅灰面，品牌块（站点 Logo 或 Bird 图标，透底无底色块）+ 站点名 + 副标题；导航项 36px 高、圆角 6px，选中项为白底 + 边框；前台导航为 首页 / 题库 / 题单 / 比赛 / 团队 / 组织 / 代码广场
2. **后台空间**：`/admin/*` 时侧栏切换为管理菜单（内容 / 社区 / 数据 / 系统 四组），底部「返回前台」；管理入口与区块仅 `admin`（tutor 已随组织化改造下线）
3. **顶栏**：56px 下边框；左侧侧栏开关 + 面包屑（<640px 隐藏），命令面板入口（Ctrl/⌘+K），右侧语言 / 明暗切换；账户菜单统一收在侧栏底部用户区（个人资料 / 管理后台 / 退出），避免与顶栏重复
4. **内容画布**：列表页使用 `WorkbenchShell` 视口锁定（工具栏 + 列表区域内部滚动）；「一行一条」的列表统一用 `LineList` 无框横线壳（表格列表经 `PaginatedTable` 接入），团队 / 组织 / 比赛 / 代码广场等网格浏览型列表仍用 `PaginatedCardGrid`；内容页使用 `PageShell`（最大 1360px 居中、自然滚动、底部留白）
5. **面包屑**：只反映真实层级（`管理后台/用户管理`、`题库/题目管理/编辑`）；`router/crumbs.ts` 为唯一解析来源
6. **命令面板**：可搜索全部前台/后台菜单与账户页；`↑↓` 选择、`Enter` 打开、`Esc` 关闭

### 响应式与移动端

- 断点统一按 Tailwind：`sm 640` / `md 768` / `lg 1024` / `xl 1280` / `2xl 1536`；`SplitPane` 内部用 `900px` 判断上下堆叠。新增布局优先复用这些断点，不另造值
- <1024：常驻侧栏隐藏，导航改 `ui/sheet` 左侧抽屉（284px / max 86vw）；<640：顶栏面包屑隐藏，搜索入口收为图标按钮
- 表格窄屏策略：`ColumnLineList` 未显式传 `minWidth` 时默认 `min-width: 640px`，窄屏**横向滚动展示全部列**，不再把列压到几像素；`Pager` 在 ≤640px 收起页码窗口（`sibling-count=0`），避免页码条溢出
- 列表工具条：`SearchFilterBar` 搜索框窄屏 `w-full`，≥640 才使用传入的 `searchWidth`；工具条整体允许换行
- 团队 / 组织详情：摘要卡文本列至少 200px 宽，操作按钮组窄屏独占一行；功能导航窄屏横排、可横向滚动（`scrollbar-none`），按钮高 40px

- 代码编辑器：窄屏 `SplitPane` 上下堆叠，右栏最小 360px；控制台控制条允许换行，必须保证「提交代码」始终可见；Monaco 在 ≤640px 自动 `wordWrap: 'on'`。Monaco 字体偏好变更必须按「显式 `document.fonts.load` 等字体 → `remeasureFonts()` 清度量缓存 → `updateOptions`」顺序应用，否则字符宽度误差会累积成光标/文本偏移；容器不设 `padding`、隐藏横向滚动条；keep-alive 返回与容器尺寸变化都要 `layout()`
- 主区滚动容器使用 `overscroll-contain`，避免移动端滚到底触发页面回弹；触控目标不低于 32px，导航 / 主操作按钮优先 40px

### 交互习惯

- 只读代码展示统一用 `ui/code-block`：`components/common/CodeBlockView.vue` 封装（语言标签 + Shiki 高亮 + 行号 + 复制），提交详情与代码广场详情直接使用；Markdown（题面 / 题解 / 公告）中的 fenced code 由 `MarkdownView` 渲染后用 Shiki 补高亮。语言映射 `cpp17 → cpp`、`python3.12 → python`、`java21 → java`，新增语言需在 `ui/code-block/highlighter.ts` 注册

- 危险操作（删除、封禁、注销、退出团队、提交）先确认再执行；统一走 `utils/feedback.ts` 的 `confirmDialog`（Promise，底层 `ui/alert-dialog`）或 `confirmAsyncDialog`
- 命令式提示统一 `utils/feedback.ts`（由 `ui/sonner` 的 Toaster 承载）：`message.success/error/warning/info/loading`；组件内不重复挂 Provider
- 图标按钮必须有 `aria-label` 或 `TooltipHint`；不单靠颜色传递状态
- 列表工具条的筛选开关统一用 `FilterCheckbox`（整行 label 可点击的勾选框），不再使用 `Switch`；配置编辑等非列表场景的布尔开关仍可用 `Switch`
- 刷新按钮统一复用 `components/common/RefreshButton.vue`（icon-only 幽灵按钮，loading 时图标自旋）；组件显式声明并转发 `click`，调用方直接用 `@click="load"` 即可，不要依赖 attrs 穿过 Tooltip 链
- 详情页按任务拆 Tabs（共享 `ui/tabs`），禁止自造按钮组；创建 / 编辑表单页统一使用无框版式，不再用 `WizardShell` 卡片外壳
- 题目预览（`views/problems/ProblemPreviewView.vue`）与评测结果（`components/submission/SubmissionResultPage.vue` + `SubmissionResult.vue`）同为 `PageShell` 无框分区：标题 + 灰色说明 + 细分隔线，刷新 / 返回放页头，统计用纯文本，代码与测试点各自成段，不再套 `rounded-xl border bg-card` 大卡片
- 团队 / 组织详情例外：`views/teams/TeamDetailView.vue`、`views/orgs/OrgDetailView.vue` 用同一上下布局（顶部摘要卡 + 下方功能卡，操作按钮与刷新按钮放在摘要卡内），下方卡内左侧为 `Button variant="ghost"` 竖排功能导航（窄屏横排置顶）、右侧为内容区（标题栏 + 各面板 `v-show` 懒挂载），不再用横向 `TabsList`；上下两张卡之间用 `mt-4` 留间距，避免贴死
- 组织 / 团队设置面板（`views/orgs/components/OrgSettingsPanel.vue`、`views/teams/components/SettingsPanel.vue`）仿 shadcn-vue-admin 设置页：标题 + 说明 + 细分隔线 + 无边框表单（`space-y-8`，字段下方说明文字、左对齐提交按钮），危险操作同样无提示框；不要再用嵌套 `rounded-xl border bg-card` 卡片包裹
- 团队创建比赛页（`views/teams/TeamContestCreateView.vue`）沿用同一无框表单：分区标题 + 分隔线，基本信息 / 比赛说明分段，底部左对齐保存与取消
- 管理后台比赛创建向导两页（`views/admin/AdminContestBasicView.vue`、`views/admin/AdminContestArrangeView.vue`）都不再使用 `WizardShell` 卡片外壳，直接写成无卡片页面（标题 + 步骤标识 + 细分隔线分区，底部左对齐操作按钮）
- 出题向导三页（`views/problems/ProblemStatementView.vue`、`ProblemCasesView.vue`、`ProblemVerifyView.vue`）同样去掉 `WizardShell`：页面直接写标题 + `WizardSteps` 步骤条 + 细分隔线，题面 / 样例测试点 / 验题分区保留各自说明，操作按钮统一放到页面底部左对齐
- 题单新建 / 编辑（`views/admin/AdminProblemSetFormView.vue`）与团队题单创建（`views/teams/TeamSetCreateView.vue`）改为同一无框表单：基础信息 / 题单说明分段，字段下方提示，底部左对齐保存与取消；页面结构与新建题目页（`ProblemStatementView`）一致——`max-w-1200` 全宽平铺，不用 WorkbenchShell 固定块、不做 960px 收窄；`components/common/WizardShell.vue` 已无引用并移除
- 系统配置（`views/admin/AdminConfigsView.vue`）与首页配置（`views/admin/AdminHomeView.vue`）同为 shadcn 设置页风格：分类导航无卡片外框，配置行只保留分隔线，海报行去卡片化，页面底部左对齐保存按钮；编辑弹窗沿用 `ui/dialog`，标题与控件尺寸与表单统一。首页轮播（`site.banners`）与系统公告（`site.announcement`）由 `/admin/home` 独立维护，系统配置的站点分类不再重复展示这两项
- 选择成员 / 初始管理员统一用 `components/common/UserEmailPicker.vue`：输入完整邮箱手动查询（按钮 / 回车），结果行点击添加、已选以标签展示可移除；查询函数由宿主注入（组织成员候选 / 管理员用户查找），不回退到手输用户 UUID
- 空态、加载、错误三态必须覆盖；列驱动列表由 `ColumnLineList` 基于 `ui/table` 渲染骨架 / 空态 / 分页，`LineList` 继续为自由插槽行列表提供骨架 / 空态 / 分页；独立面板使用 `EmptyState` / `ErrorState`；列表空态容器统一用 `.list-empty`（`main.css`：`flex:1` 撑满剩余高度 + 双向居中），禁止各页另写 `grid place-items-center` 或不同高度，避免空态位置漂移
- 前台实体卡片（团队 / 组织 / 比赛 / 代码广场）沿用旧 UI 的简约范式：单行头部（头像 + 名称 + 角色 / 状态点标）、描述最多两行截断、底部两行（元信息行：成员数 / 题数 / 语言；`border-t` 细分隔线；时间行：创建 / 更新时间，11px `tabular-nums`）；不放「查看 / 申请加入」行动文案、右箭头或重复徽标，整卡点击即交互；卡片 `rounded-md border bg-card`、无阴影
- 编辑器字号 / 字体偏好来自用户资料（`editor_font_size` / `editor_font_family`），`CodeEditor` 统一消费，个人资料页保存后即时生效
- `CodeEditor` 自身不设最小高度（`min-h-0`），由父容器给定高度；需要最小高度时在父级 `min-h-*` 声明，避免嵌套最小高度叠加导致相邻面板溢出

### 列表工作台

- 页面结构：`WorkbenchShell` → `#toolbar` 放 `SearchFilterBar`，列表筛选条件（状态 / 类型等）统一用 `ui/select` 下拉并与搜索框同行，**不再用 Tabs 做筛选**（Tabs 仅用于详情页内容分区）→ `LineList`（表格列表经 `PaginatedTable`）或 `PaginatedCardGrid`；前台题库列表（`views/problems/ProblemListView.vue`）同样走 `PaginatedTable`，保留筛选、标签显隐、分页与空 / 加载态
- 列表列定义：`AppTableColumn<T>`（`key/title/width/align/cell`）；`ColumnLineList` 基于 shadcn `ui/table` 由列定义生成表头 / 行（含勾选、行点击、骨架），表头统一 40px 高且用 `bg-surface`；`PaginatedTable` = `ColumnLineList` + 分页开关；无分页的列驱动列表直接用 `ColumnLineList`，自由插槽列表用 `LineList` 的 `#item` 插槽；旧的 `DataTable.vue` 已移除，禁止各页手写原生 `<table>` 或 `divide-y` 列表壳，统一经 `ColumnLineList` / `PaginatedTable` / `LineList`
- 卡片列表：`PaginatedCardGrid` 负责响应式网格（1 / 2 / 3 / 4 列）、骨架、空态与分页；领域卡片用 `EntityCard` 作为整卡可点击外壳（支持 Enter / Space 与可见焦点环），卡片内展示头像、标题、状态徽标、简介与 1–2 行元信息
- 比赛卡片与代码分享卡片保持极简：头像 / 图标 + 标题 + 两行简介 + 纯文本元信息；比赛的起止时间单独一行，赛制 / 题数 / 报名人数另起一行，代码卡片是语言 / 作者 / 更新时间一行；只在确有必要时保留一个状态徽标，不用信息栏、箭头、多个彩色徽标或图标行堆砌，hover 只轻微描边
- 首页沿用旧版的全屏气势：内容铺满主区宽度，上半部为主视觉（桌面高 `52dvh`，`min 340px` / `max 580px`，海报轮播 / 品牌横幅 2fr + 公告 1fr，最小 260px），下半部入口磁贴与小贴士按内容自然高度排布；内容超出视口时由主区滚动，不用 flex 拉伸压缩卡片，避免卡片重叠；窄屏同样自然高度滚动，不收窄成中间栏
- `views/home/HomeCarousel.vue`：自动播放间隔 5s，海报异步加载后自动启动；不渲染左右箭头，只保留底部圆点切图；鼠标悬停不暂停；手动点圆点后重置计时；切换用 420ms 交叉淡入淡出，加载过的图片保持挂载避免空窗；移动端容器固定 `aspect-video` 且图片 `object-contain`，保证海报完整可见（桌面仍 `object-cover` 满铺）
- 列表形态选择：列驱动列表（管理后台列表、提交、日志、测试点 / 比赛单元格明细等）统一由 `ColumnLineList` / `PaginatedTable` 基于 `ui/table` 渲染 shadcn 表格；自由插槽的「一行一条」列表继续用 `LineList` 无框横线壳；网格浏览型实体（团队 / 组织 / 比赛 / 代码广场）继续用 `PaginatedCardGrid`
- 搜索统一手动触发：输入只同步关键词，点击「查询」或回车才发起；清空（X）立即按空关键词重查
- 题库列表的标签列可在工具条勾选显示 / 隐藏，偏好写入 localStorage（`pigeonoj.problems.showTags`），切换不重新请求
- 分页：`LineList`（`showPager` 开启，分页列表经 `PaginatedTable`）与 `PaginatedCardGrid` 统一内置 `Pager`（页码窗口、总数、可选每页条数）；无分页列表不要开 `showPager`；页面只维护 `usePagination()` 的 page / pageSize / total，慢响应用 `beginLoad/isCurrent` 守卫
- 批量操作：`PaginatedTable` 支持可选 `selectable / rowKey / selectedKeys`（跨页保留勾选）；不使用时零影响
- 行 / 卡片点击进入详情时保持上下文路由，不跳出当前业务区块

### 按钮与表单

- 每个操作区域最多一个主按钮；次要操作用 `outline` / `ghost`；危险操作用 `destructive`
- 工具条按钮统一 `size="toolbar"`（36px，与 `h-9` 输入框 / 选择器同高）；对话框内操作保持 `size="sm"`，不再用 `class="h-9"` 临时抬高
- 表单 `Label` 置顶；必填/范围用控件属性与提交前校验；提交按钮 loading 用 `Loader2` 自旋 + 禁用
- 表单内的编辑器工具栏按钮（如 `MarkdownEditor` 的加粗 / 预览切换）必须显式 `type="button"`，避免浏览器默认 `submit` 误触发表单保存
- 弹窗使用 `ui/dialog`（受控 `v-model:open`），必须有 `DialogTitle`（可 `sr-only`）；输入型确认（封禁原因、密码）在弹窗内完成

### 「题面 + 编辑器」双栏工作台

- `components/common/SplitPane.vue`：桌面端左右独立滚动、分隔条可拖拽且比例持久化（双击复位）；<900px 自动上下堆叠
- `components/problem/ProblemWorkbench.vue`：左题面（`ProblemMetaBar` + `ProblemStatement`），右编辑器 + 自测控制台；上方工具行「语言」靠左、「我的提交 / 题解」靠右，「自测运行 / 提交」放进下方控制台标题行，避免顶部拥挤
- 自测控制台常驻编辑器下方，形态对齐旧 UI（naive-ui 版）：面板顶部中央 64×14 凹口把手（单击开合、按住拖拽调高，位移 <3px 仍视为单击；方向键 / Home 微调与复位），默认展开 440px、下限 140px，收起态只留约 47px 控制条；点击当前已展开的 tab 会收起面板；控制条内 tab 后紧接「自测运行」，右侧「提交代码」，运行后自动切到结果并展开；展开态拖得过小视为取消并还原高度；高度按 px 持久化到 `pigeonoj.problems.consoleHeight.v2`（兼容旧键 `pigeonoj.problems.consoleHeight`）；结果含状态、耗时、内存与输出/报错
- 提交历史经 `components/problem/MySubmissionsDialog.vue` 懒加载分页（弹窗 `sm:max-w-[760px]`、高 `min(72vh, 520px)`，保留完整列），行点击进入上下文内评测结果页

### 可访问性

- 图标按钮必须有可见文字、`aria-label` 或 Tooltip；弹窗焦点留在弹窗内
- 状态标签含文本；键盘可聚焦；命令面板 / 弹窗支持 Esc 关闭

## 组织与社区

- **组织中心**：`/orgs/mine` 列表 + `/orgs/:orgId` 详情（成员 / 组织团队 / 组织题库 / 设置）；组织管理员可拉人、授管理员、建团队、维护组织题库；组织题目路由固定为 `/orgs/:orgId/problems/...`，读题 / 交题 / 自测全部留在组织上下文
- **团队创建**：唯一入口为组织详情「创建团队」（`POST /orgs/{orgId}/teams`）；团队题目只来自组织题库 / 全站公开的引用快照，团队中心仅浏览与申请
- **社区**：题解页随题目上下文挂载（题库 / 题单 / 比赛 / 组织各自 `/solutions/*` 路由），官方题解收口题解页 Tab；题解分享列表采用 `LineList` 无框横线列表（作者头像 + 标题 + 摘要 + 作者/日期 + 评论数，行间 `divide-y` 横线，非表格）；代码广场 `/codes` 列表 / 分享 / 详情，编辑 `/codes/:id/edit` 为详情的下级路由（面包屑：代码广场 / 代码分享详情 / 编辑分享，其中详情项链接回 `/codes/:id`）；评论与举报统一 `components/community/CommentThread.vue` / `ReportDialog.vue`
- **管理治理**：`/admin/orgs`、`/admin/solutions`、`/admin/codes` 分别负责组织、题解、代码分享；题解预览弹窗内可直接治理评论

## Markdown 渲染

- 题面 / 公告 / 题解统一 `components/common/MarkdownView.vue`（markdown-it `html:false` + DOMPurify 白名单 + KaTeX）
- 编辑统一 `components/common/MarkdownEditor.vue`（textarea + 工具栏 + 写/预览切换 + 粘贴/选择图片上传）；存储仍为纯 Markdown
- 插图：`POST /files/upload/image`（登录用户，≤5MB，JPG/PNG/WEBP/GIF），题面展示限宽 50%
- 禁止对用户可控内容直接 `v-html`（仅 MarkdownView 内部经白名单渲染）

## 国际化

- 所有用户可见静态文案位于 `src/frontend-next/src/i18n/locales/`，使用 `t('key')`；禁止硬编码自然语言
- 每个 key 必须同时提供 `zh-CN` 与 `en-US`；`src/i18n/keys.spec.ts` 会扫描模板 / 路由中的静态 key，缺失即测试失败
- 覆盖范围：路由标题、导航、按钮、表单标签与 placeholder、表格列、状态字典、筛选项、空状态、弹窗、Toast、兜底错误、CSV 导出的表头

## 共享组件

| 组件 | 用途 |
| --- | --- |
| `components/common/BaseAvatar.vue` | 头像 / Logo：空值或加载失败回退默认图（user/team/contest） |
| `components/common/LineList.vue` | 自由插槽的无框横线列表壳：表头 / 逐行分隔线 / 骨架 / `.list-empty` 空态 / 可选分页，支持 `#item` 行插槽 |
| `components/common/ColumnLineList.vue` + `table-types.ts` | 列驱动的 shadcn 表格：由 `AppTableColumn` 生成 `ui/table` 表头 / 行 / 勾选 |
| `components/common/PaginatedTable.vue` | `ColumnLineList` + 分页开关，供所有分页列表使用 |
| `components/common/PaginatedCardGrid.vue` + `EntityCard.vue` | 统一卡片列表壳（响应式网格 / 骨架 / 空态 / 分页）与整卡可点击外壳 |
| `components/common/Pager.vue` | 独立分页条（页码窗口 + 总数 + 可选每页条数） |
| `components/common/EmptyState.vue` / `ErrorState.vue` | 统一空态 / 加载失败态（可带重试与操作） |
| `components/common/InlineNotice.vue` | 语义提示条（info / success / warning / danger / neutral） |
| `components/common/DateTimeField.vue` | 统一 `datetime-local` 输入（时间戳模型 + 清空） |
| `components/common/SearchFilterBar.vue` | 搜索框 + 筛选控件插槽 + 「查询」+ 右侧动作区 |
| `components/common/RefreshButton.vue` | 刷新按钮（loading 自旋） |
| `components/common/FilterCheckbox.vue` | 列表工具条勾选筛选（整行可点击，`update:modelValue`） |
| `components/common/WorkbenchShell.vue` / `PageShell.vue` | 视口锁定列表壳 / 自然滚动内容壳 |
| `components/common/StatusTag.vue` / `ToneBadge.vue` | 提交状态 / 通用语义徽标（色值统一取自 `tone.ts`） |
| `components/common/MarkdownView.vue` / `MarkdownEditor.vue` | Markdown 渲染 / 编辑 |
| `components/common/CodeEditor.vue` | Monaco 编辑器（Python/C++/Java 按需语言包） |
| `components/common/SplitPane.vue` | 可拖拽双栏（题面 / 编辑器） |
| `components/common/EmailCodeInput.vue` | 邮箱验证码输入 + 60s 倒计时 |
| `components/problem/*` | 题目元信息、题面、样例、工作台、提交历史、标签选择、测试点导入 |
| `components/submission/SubmissionResult.vue` | 评测结果页统一展示（统计 / 代码 / 测试点） |
| `components/problemsets/ProblemPicker.vue` | 题库选择弹窗（默认仅本人；loader 支持团队候选源） |
| `components/contests/*` / `components/teams/*` | 比赛 / 团队领域共享展示组件 |
| `components/community/CommentThread.vue` / `ReportDialog.vue` | 评论（含回复 / 举报 / 管理恢复）与举报弹窗 |
| `views/orgs/*` / `views/community/*` | 组织空间与社区页面 |
| `layout/*` | 应用壳、侧栏、顶栏、命令面板、面包屑、语言 / 主题 / 用户菜单 |

## 代码组织

```text
src/frontend-next/
  eslint.config.js       # ESLint flat config（Vue + TS）
  .prettierrc.json       # Prettier（格式化唯一权威）
  vite.config.ts         # Vite + Vitest
  src/
    api/                 # 统一 HTTP 与领域 API
    assets/              # 设计令牌、Monaco 覆盖样式、默认头像
    components/
      common/            # 通用展示 / 工作台组件
      ui/                # shadcn-vue 原子组件（reka-ui）
      problem/ submission/ problemsets/ contests/ teams/  # 领域组件
    composables/         # 分页 / 防抖草稿 / 自测 / 轮询等
    constants/ i18n/ layout/ monaco/ router/ stores/ types/ utils/
    views/               # 路由页面（按领域分目录；大页拆 components/ 子组件）
```

- 页面组件管理请求、筛选、弹窗、本页状态；展示组件 props / emits / 插槽工作
- 单文件目标 < 350 行；大详情页按任务拆 Tabs 子组件，禁止复制粘贴整段模板
- 通过 `api/` 调用后端，统一处理 `{ code, message, data }` 信封
- 样式优先 Tailwind 原子类 + 设计令牌；组件内复杂样式才写 scoped CSS
- 不在组件中硬编码环境 URL、密钥、Token 或权限绕过逻辑

## 工具链与质量门禁

| 工具 | 命令 | 说明 |
| --- | --- | --- |
| ESLint | `npm run lint:check` / `npm run lint` | 静态检查 / 自动修复 |
| Prettier | `npm run format` | 一键格式化 |
| Vitest | `npm test` | 单元测试（jsdom；含 i18n 静态 key 完整性） |
| 类型检查 + 构建 | `npm run build` | `vue-tsc -b` + `vite build` |

- 工作目录：`src/frontend-next`；格式类规则统一交给 Prettier，ESLint 关闭重叠规则
- 模板内联事件禁止多条语句（Prettier 折行会生成非法表达式），多语句逻辑写方法
- `@typescript-eslint/no-explicit-any` 暂关闭

## 路由与导航

- 一级侧栏是业务区块入口；子路由激活时一级菜单保持激活
- 对象上下文页面（创建题目、编辑、提交详情、评测结果）标记 `meta.contextPage: true` + `meta.hidden: true`；归属工作台用 `breadcrumbParent` 声明
- 路由标题 / 菜单标题设 `meta.titleKey`，由 i18n 生成；无 `titleKey` 的路由不得进导航目录
- 浏览器标签「页面标题 · 站点名」，favicon 取 `site.logo`

### 页面实例缓存（列表状态保留）

`AppLayout.vue` 对 `router-view` 采用插槽分流：声明 `meta.keepAlive: true` 的页面进入 `<KeepAlive>`（实例 key 为 `route.fullPath`），从上下文页返回时保留筛选、页码和已加载数据；`:max=8` LRU 兜底；缓存 key 绑定当前登录用户 id，登出 / 换号后整体作废。滚动容器是 `main`，每次导航由 `AppLayout` 重置到顶部，滚动位置不保留。

- 缓存范围（`meta.keepAlive: true`）：各列表 / 工作台（题库、题单、比赛、团队、组织、代码广场、管理后台列表与在线用户），以及评测结果页
- 不缓存：所有详情页、编辑页、上下文写题页、题目预览、邀请页、个人资料 / 安全设置等；进入即重新拉取，避免旧数据
- 写题代码不依赖页面缓存：按「用户 + 题目 + 语言」经 `useCodeDraft` 持久化到 localStorage，离开 / 刷新均可恢复
- 评测结果页的轮询必须在 `onDeactivated` 暂停、`onActivated` 恢复；在线用户列表同理
- 面包屑层级解析收敛于 `router/crumbs.ts` 的 `buildCrumbs`；新增页面默认不缓存，仅列表 / 工作台可声明 `meta.keepAlive`
- 数据时效由各列表页刷新按钮兜底；退出 / 解散团队经 `stores/teams` 脏标记在列表页 `onActivated` 重拉

### 路由上下文隔离（契约级规范）

同一资源页面被多个业务上下文复用（题目详情 / 评测结果 / 预览 × 题库、题单、比赛、团队）时，每个上下文拥有独立路由实例，上下文内的所有导航与交互必须封闭在本上下文路由内，**禁止把用户带离当前业务上下文**。实例：题库 `/problems/:id`、题单 `/problem-sets/:setId/problems/:problemId`、比赛 `/contests/:cid/problems/:problemId`、团队 `/teams/:teamId/problems/:problemId`、团队题单 `/teams/:teamId/sets/:setId/problems/:pid`、团队比赛 `/teams/:teamId/contests/:cid`（详情 / 编辑向导 / 赛时工具 / 内题目 / 内评测结果）、管理后台 `/admin/problem-sets/:id/problems/:pid/preview`。

规则：

1. **上下文路由独立**：每个上下文为自己的 URL 前缀下声明路由（页面组件可复用），上下文专属路由声明在所属业务区块的 children 内，紧随其列表 / 详情路由之后
2. **禁止跨上下文跳转**：进入下一层、返回上一层、提交后跳转都必须落在本上下文路由内；管理端点击资源仅打开只读预览
3. **组件复用取参**：复用组件按「上下文参数优先」取参（如 `route.params.problemId ?? route.params.id`），内部链接基于上下文动态构造（如评测结果基路径 `submissionsBase`）
4. **配套后端上下文端点（模块统一入口）**：上下文内对资源的读 / 写调用本上下文模块的专属端点，不跨模块直调；端点在入口校验资源归属关系
5. **面包屑真实层级**：`breadcrumbParent` 支持函数动态解析路径与数组多级父链，中间级必须可点击回跳
6. **管理端只读隔离**：管理后台的资源浏览页点击资源仅打开只读预览，管理操作收敛在 `/admin`
7. **新增上下文时同步契约**：引入新的上下文路由必须同步更新 `docs/contracts/` 对应模块契约

## 前端验收

每次前端变更至少完成：

1. `npm run lint:check`（+ `npm run format`）
2. `npm run build`（类型检查 + 构建）
3. `npm test`（Vitest；utils / api / i18n key 完整性）
4. 涉及界面时，中英文 + 亮暗主题 + 窄屏 + loading/error/empty 双语言检查
5. 涉及路由时，验证侧栏激活、子跳转、标题、权限过滤
6. 涉及 i18n 时，确认无硬编码文案（`src/i18n/keys.spec.ts` 必须通过）