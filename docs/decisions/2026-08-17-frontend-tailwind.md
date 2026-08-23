# 引入 Tailwind CSS（v4）作为前端样式辅助工具

日期：2026-08-17
状态：已采纳

## 背景

前端 UI 主要依赖 Element Plus（组件样式），但页面布局（间距 / 弹性布局 / 响应式 / 排版）仍散落在各
视图的 scoped CSS 中，存在风格漂移与重复样板。拟引入 Tailwind CSS 统一布局层样式。

## 决策

引入 **Tailwind CSS v4**（`tailwindcss` + `@tailwindcss/vite`），与 Element Plus **共存**：

- **定位**：组件样式归 Element Plus，页面布局 / 间距 / 排版归 Tailwind（原子类）
- **暗色模式**：对齐 Element Plus 的 `html.dark` class 策略，通过
  `@custom-variant dark (&:where(.dark, .dark *))` 让 Tailwind `dark:` 变体与 EP 暗色变量同步
- **preflight**：保留（EP 组件自身会恢复基础样式），个别冲突处微调
- **配置**：仅 Vite 插件 + CSS 一行 `@import "tailwindcss"`，不引入 Tailwind v3 的 tailwind.config / postcss 链

## 备选方案

1. **不引入**：现有自定义样式量不大，避免双体系维护成本 —— 被否：布局样式仍会持续增长
2. **Tailwind v3（postcss + tailwind.config.js）**：配置更繁琐，且与 v4 相比无优势 —— 被否
3. **CSS Modules / styled-components**：与 Vue SFC scoped 思路重叠，收益低 —— 被否

## 影响

- `docs/architecture.md`：技术栈表 + 前端约定补充「样式约定」
- 新增依赖：`tailwindcss`、`@tailwindcss/vite`（前端 devDependencies）
- 改造节奏：以 HomeView 与 admin 工具栏为样板，其余页面渐进替换（不强制一次性重构）

## 后续关注

- preflight 与 Element Plus 的已知小冲突点（按钮 / 表单 margin）若出现回归，按需加局部覆盖
- 暗色模式下 `dark:` 变体需与 EP 变量共存，注意对比度
