# FPS 题库导入（`import_fps_problems.py`）

从 freeproblemset（HUSTOJ 题库交换格式，fps XML）初始化种子题目，**直写 DB + MinIO**，
不走 API 验题流程。解析 / 入库核心在 `app/services/problem_import.py`，与
`POST /admin/problems/import` 管理端点（题目管理页「导入 ZIP」按钮）共用同一实现：

```bash
cd src/backend
python -m scripts.import_fps_problems --dry-run <fps.xml | fps.zip | URL> ...  # 只解析预览
python -m scripts.import_fps_problems --limit 50 <数据源> ...                  # 实际导入
```

## 数据源

- 本地 `.xml` / `.fps` / `.zip` / **目录**（递归收集）或 URL
- `github.com/blob/...` 链接自动转 raw，raw 不可达时回退 api.github.com（返回 HTML 页面会被嗅探跳过）
- TK 题库（tk.hustoj.com，HUSTOJ FPS 包）下载的 zip 可直接整目录导入

## 行为规则

- 题面 / 说明按原文存 Markdown 字段（FPS 为 HTML 片段，前端 markdown-it 可渲染）；
  标程（`solution`）以代码块形式存入官方题解；`hint` → 题面说明，`source` → 题目背景
- **有测试点的题 → published**（回填 `verified_at`，直接可做）；**无测试点 → draft**
  （无测试点无法判题，须人工补点走验题后发布）
- 带 `spj` 特判的题默认跳过；`--include-spj` 时 checker 源码写**暂存集**并导入为**草稿**
  （验题通过后 apply 晋升生效；`<spj>` 仅有标记无源码的题仍跳过）
- 同名题跳过（幂等，可重跑）；`--owner-email` 指定归属用户，缺省取首个全局 admin
- 需本地 PG / MinIO 已启动且迁移已执行；单侧测试点 >8MB / 样例 >64KB 按契约上限丢弃