# LibreOJ 题目爬取（`crawl_loj.py`）

从 LibreOJ（loj.ac，开放数据 OJ）按题号区间抓取题面 / 样例 / 测试点，
输出 FPS XML 到 `<仓库根>/loj_problems/`，经 `import_fps_problems.py` 导入：

```bash
cd src/backend
python -m scripts.crawl_loj --list-only --begin 100 --end 199   # 只列题目
python -m scripts.crawl_loj --begin 100 --end 199               # 抓取
python -m scripts.import_fps_problems ..\loj_problems           # 导入
```

## 参数

| 参数 | 说明 |
| --- | --- |
| `--begin` / `--end` | 起始 / 结束题号（区间抓取，二选一与 `--ids` 互斥） |
| `--ids 100 101` | 显式题号列表 |
| `--list-only` | 只列区间内题目，不抓数据 |
| `--delay` | 请求间隔秒数（默认 1s，礼貌爬取） |
| `--token` | loj.ac 登录 token，仅个别题数据需要登录（取自网页 localStorage.appState） |
| `--out` | 输出目录（默认 `<仓库根>/loj_problems`） |

## 行为规则

- 自定义 checker（SPJ）的题照常下载并按标准比对导入，同时警告（平台无 SPJ）
- 文件输入输出（fileIo）的题跳过（平台仅 stdin/stdout）
- 带子任务绑定的题照常导入并警告（判题退化为按测试点比例计分）
- 题号写入标题前缀（`LOJ{id}. {title}`）保证导入去重
- 输出为每题一个 FPS XML，可直接喂给 `import_fps_problems.py`