# 决策：前端视觉风格统一为 Notion 风格

- 日期：2026-08-24
- 状态：**已被取代** —— 由 `docs/decisions/2026-08-24-naive-ui-nova-style.md`（Naive UI + vue-fastapi-admin 风格）取代，以下内容仅作历史记录。
- 影响范围：`src/frontend/src/assets/main.css`、所有 `.vue` 组件 scoped CSS、Element Plus 主题 token 映射、文档 `docs/frontend.md`

## 背景

前端早期采用品牌蓝 `#3867f4` 主色、渐变视觉面板、圆角 12px+ 卡片与悬浮位移/缩放动画，
视觉语言零散、与“长时间管理任务易扫描”的产品目标不符。本次重构将前端统一收敛到
**Notion 风格**这一单一设计语言，降低认知负担、提升信息密度与一致性。

## 决策

采用 Notion 风格作为唯一视觉语言，硬规则如下（违反即视为缺陷）：

1. **色板**：画布 `#f7f6f3`、表面 `#ffffff`、悬停 `#efedea`、激活 `#e3e1db`、边框 `#e5e7eb`、
   文字 `#37352f` / `#787774` / `#9b9a97`；强调色蓝 `#2eaadc`、红 `#eb5757`、绿 `#0f7b6c`、黄 `#dfab01`。
   禁止品牌蓝 `#3867f4`、紫 `#7d55da` 等鲜艳色。
2. **禁止渐变**：任何 `linear-gradient` / `radial-gradient` 均不允许（ESLint 自定义规则已拦截）。
3. **圆角**：默认 6px，大卡片 10px，小标签 4px；禁止 `rounded-2xl/3xl/full`（头像除外）。
4. **触感（克制）**：悬停只变背景色（Block Highlighting），激活用更深米色 + 深色文字（Micro-click），
   过渡仅 `transition-colors`（150ms）；禁止 `translate/scale` 动画、阴影跳变、hover 边框加粗。
5. **拖拽手柄错觉**：可拖拽卡片/列表项用 `.notion-card-group`（组 hover 时左侧 `⋮⋮` 手柄浮现），
   不做彩色拖拽条。
6. **字体**：系统字体栈，不引入 Inter 等外部字体；禁用大写字母 + `letter-spacing` 的眉题样式。
7. **Token 唯一来源**：所有颜色/圆角/阴影/聚焦环来自 `assets/main.css` 的 `:root` + `html.dark`
   变量，并映射 Element Plus `--el-*` 变量；组件禁止硬编码色值。

## 设计 Token 来源

- `assets/main.css`：`:root`（亮色）与 `html.dark`（暗色）定义全套 `--app-*` CSS 变量，
  并覆盖 `--el-color-*`、`--el-border-radius-*`、`--el-box-shadow-*` 等 EP 变量。
- 共享类：`.page-stack` / `.section-title` / `.form-hint` / `.result-box` / `.notion-card-group`
  统一定义在 `main.css`，各视图复用。

## 验收

- `npm run lint:check`：自定义规则禁止 `gradient()`，并复用既有风格检查。
- `npm test` / `npm run build`：保持全绿（25 用例通过、构建成功）。
- 中英文、窄屏（<768px）、loading/error/empty 状态分别核查，无渐变、无悬浮位移、无鲜艳主色。

## 反模式（禁止）

- 渐变背景的登录/注册视觉面板（改为 Notion 分栏：米色画布 + 白色表单卡）。
- 悬停上浮（`translateY(-3px)`）、彩色阴影、圆形药丸头像按钮。
- 大写字母 + `letter-spacing` 的眉题；非标准字重（如 620/680/750，统一为 400/500/600/700）。
