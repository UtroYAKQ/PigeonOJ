# 题面 Markdown 渲染（markdown-it + DOMPurify）

日期：2026-08-23
状态：已采纳

## 背景

契约（`docs/contracts/problems.md` 数据模型）将题面 / 输入输出说明 / 官方题解定义为
Markdown（TEXT 字段），但前端详情页一直按纯文本 `white-space: pre-wrap` 展示，
代码块、列表、表格、链接等题面常用排版无法呈现。

## 决策

引入 **markdown-it** + **dompurify** 两个前端依赖，新增 `src/utils/markdown.ts`
与 `src/components/MarkdownView.vue`：

- **渲染配置**：`html: false`（原始 HTML 按文本转义）、`linkify: true`；
  渲染结果再经 DOMPurify 白名单过滤（禁 `script/iframe/form/style/input`），
  双重防 XSS —— 出题人可写 Markdown，但不可注入 HTML。
- **样式**：`MarkdownView.vue` scoped 排版样式，颜色 / 圆角 / 边框全部使用
  `--app-*` 设计变量，自动适配明暗主题。
- **定位**：仅用于题目相关富文本展示（题面 / 说明 / 题解）；社区帖子等模块
  后续复用同一组件，不另起炉灶。

## 备选方案

1. **继续纯文本展示**：零依赖 —— 被否：与契约定义的 Markdown 题面长期不符，
   数学公式与代码块场景无法支持。
2. **marked + DOMPurify**：更小 —— 被否：marked 对 GFM 表格等支持需插件拼装，
   markdown-it 单包覆盖且是 Vue 社区事实标准。
3. **服务端渲染 HTML**：后端引入渲染链并存储产物 —— 被否：增加后端攻击面与
   缓存失效复杂度；客户端渲染足够。

## 影响

- `docs/frontend.md`：设计系统补充 Markdown 渲染约定
- 新增依赖：`markdown-it`、`dompurify`、`@types/markdown-it`（前端 dependencies）
- 题目详情页题面区块由多卡片改为单卡内分节（配合可拖拽分栏布局）

## 后续关注

- 若题面需要数学公式（LaTeX），再评估 KaTeX 按需接入，不在本次范围
- `linkify` 自动链接经 DOMPurify 过滤后保留 `href` 白名单属性，注意外链
  未来如需中转页提示再调整
