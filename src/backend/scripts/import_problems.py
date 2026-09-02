"""批量导入本地题库（problems/<年份>/<题目录>）到线上 OJ。

与页面操作等价的完整链路（走平台正规验题门禁，不绕过任何状态机）：
  创建草稿 → 上传暂存测试点 → 写入展示样例 → 发起验题
  → std.py 验题提交（按暂存集判题）→ 轮询至 AC
  → 测试点晋升生效 → 发布

目录约定（见 problems/README.md）：
  <题目录>/description.md   题面（h1 标题 + ## 输入格式 / ## 输出格式 / ## 样例输入[ 2] / ## 样例输出[ 2] / 其余节并入题面）
  <题目录>/std.py           标准程序（Python 3，stdin → stdout）
  <题目录>/NN.in + NN.out   测试点（成对出现才导入，文件名按数字排序）

用法（仓库根目录）：
  $env:PIGEONOJ_IMPORT_TOKEN = "<会话 token>"
  python src/backend/scripts/import_problems.py [--dry-run] [--skip-verify] [--only 关键字 ...]

- --dry-run     只解析题面与测试点并打印，不发起任何请求
- --skip-verify 建草稿 + 传测试点 + 写样例后停止（验题 / 晋升 / 发布在页面上人工做）
- --only        按路径子串过滤，如 --only suzhou_2025/01
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBLEMS_DIR = REPO_ROOT / "problems"
DEFAULT_BASE = "https://www.youtro.top/api/v1"
LANGUAGE = "python3.12"

# description.md 小节标题 → 用途映射（同义写法归一）
INPUT_HEADINGS = {"输入格式", "输入描述"}
OUTPUT_HEADINGS = {"输出格式", "输出描述"}
SAMPLE_IN_RE = re.compile(r"^样例输入(?:\s*(\d+))?$")
SAMPLE_OUT_RE = re.compile(r"^样例输出(?:\s*(\d+))?$")
# 其余小节（数据范围 / 说明 / 提示 / 样例解释 …）按原文并入题面尾部
SOURCE_RE = re.compile(r"\*\*来源[：:]\s*(.+?)\*\*")


def split_sections(text: str) -> tuple[str, str, list[tuple[str, str]]]:
    """把 markdown 按 '## ' 分节；返回 (标题, 首段正文, [(小节标题, 小节原文)])。"""
    lines = text.splitlines()
    title = ""
    intro: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_head: str | None = None
    for line in lines:
        if line.startswith("# ") and not line.startswith("## ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            current_head = line[3:].strip()
            sections.append((current_head, []))
            continue
        if current_head is None:
            intro.append(line)
        else:
            sections[-1][1].append(line)
    return title, "\n".join(intro).strip(), [(h, "\n".join(body).strip()) for h, body in sections]


def strip_fence(body: str) -> str:
    """去掉小节中的 ``` 围栏（保留内部内容，去掉围栏行）。"""
    out = [line for line in body.splitlines() if not line.strip().startswith("```")]
    return "\n".join(out).strip()


class ParseError(Exception):
    pass


def parse_problem(dir_path: Path) -> dict:
    md_path = dir_path / "description.md"
    if not md_path.exists():
        raise ParseError("缺少 description.md")
    if not (dir_path / "std.py").exists():
        raise ParseError("缺少 std.py")
    text = md_path.read_text(encoding="utf-8")
    title, intro, sections = split_sections(text)

    input_desc = ""
    output_desc = ""
    samples: dict[int, dict[str, str]] = {}
    tail_sections: list[tuple[str, str]] = []
    source = ""
    m = SOURCE_RE.search(text)
    if m:
        source = m.group(1).strip()

    for head, body in sections:
        if head in INPUT_HEADINGS:
            input_desc = body.strip()
        elif head in OUTPUT_HEADINGS:
            output_desc = body.strip()
        elif SAMPLE_IN_RE.match(head):
            idx = int(SAMPLE_IN_RE.match(head).group(1) or 1)
            samples.setdefault(idx, {})["input"] = strip_fence(body)
        elif SAMPLE_OUT_RE.match(head):
            idx = int(SAMPLE_OUT_RE.match(head).group(1) or 1)
            samples.setdefault(idx, {})["output"] = strip_fence(body)
        else:
            tail_sections.append((head, body))

    if not (title and input_desc and output_desc):
        raise ParseError(f"题面缺必要字段：title={bool(title)} input={bool(input_desc)} output={bool(output_desc)}")

    description = intro or title
    for head, body in tail_sections:
        description += f"\n\n## {head}\n\n{body}"

    sample_list = [
        {"input": samples[i].get("input", ""), "output": samples[i].get("output", "")}
        for i in sorted(samples)
    ]
    for s in sample_list:
        if not s["input"] or not s["output"]:
            raise ParseError("样例输入/样例输出不完整")

    background = source or "苏州大学预推免机试真题"
    cases = load_cases(dir_path)
    if not cases:
        raise ParseError("没有成对的 NN.in / NN.out 测试点")
    std_code = (dir_path / "std.py").read_text(encoding="utf-8")
    if len(std_code.encode("utf-8")) > 64 * 1024:
        raise ParseError("std.py 超过 64KB 提交上限")
    return {
        "title": title,
        "background": background,
        "description": description,
        "input_description": input_desc,
        "output_description": output_desc,
        "samples": sample_list,
        "cases": cases,
        "std_code": std_code,
    }


def load_cases(dir_path: Path) -> list[dict]:
    inputs = {}
    for f in dir_path.glob("*.in"):
        inputs[f.stem] = f
    cases = []
    for stem in sorted(inputs, key=lambda s: (len(s), s)):
        out_path = dir_path / f"{stem}.out"
        if not out_path.exists():
            print(f"    ! 跳过 {stem}.in：缺少 {stem}.out", file=sys.stderr)
            continue
        inp = inputs[stem].read_text(encoding="utf-8")
        out = out_path.read_text(encoding="utf-8")
        if len(inp.encode("utf-8")) > 2 * 1024 * 1024 or len(out.encode("utf-8")) > 2 * 1024 * 1024:
            print(f"    ! 跳过 {stem}：内容超过 2MB 上限", file=sys.stderr)
            continue
        cases.append({"name": stem, "input": inp, "expected_output": out, "sort_order": len(cases)})
    return cases


class Client:
    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"

    def call(self, method: str, path: str, **kwargs) -> dict:
        resp = self.session.request(method, f"{self.base}{path}", timeout=120, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}")
        envelope = resp.json()
        if envelope.get("code") != 0:
            raise RuntimeError(f"{method} {path} -> code={envelope.get('code')}: {envelope.get('message')}")
        return envelope.get("data")

    def my_problems(self) -> dict[str, str]:
        """我名下题目 {标题: id}（mine 视角含全部状态）。"""
        out: dict[str, str] = {}
        page = 1
        while True:
            data = self.call("GET", "/problems", params={"scope": "mine", "page": page, "page_size": 100})
            for item in data.get("items", []):
                out[item["title"]] = item["id"]
            if page * 100 >= data.get("total", 0):
                break
            page += 1
        return out

    def upload_cases(self, problem_id: str, cases: list[dict]) -> None:
        """暂存测试点：首点 PUT 建基线，其余逐点 PATCH 增量追加。

        单请求 payload 控制在单个测试点量级（≤ ~2MB），避免宝塔 nginx/WAF 掐断大 JSON。
        """
        first = cases[0]
        self.call("PUT", f"/problems/{problem_id}/test-cases", json={"cases": [first]})
        if len(cases) > 1:
            self.call("PATCH", f"/problems/{problem_id}/test-cases", json={"upserts": cases[1:]})


def verify_and_publish(client: Client, problem_id: str, parsed: dict) -> str:
    client.call("POST", f"/problems/{problem_id}/verify", json={})
    created = client.call(
        "POST", f"/problems/{problem_id}/verify", json={"code": parsed["std_code"], "language": LANGUAGE}
    )
    submission_id = created["submission_id"]
    terminal = {"accepted", "wrong_answer", "time_limit_exceeded", "memory_limit_exceeded",
                "output_limit_exceeded", "runtime_error", "compile_error", "system_error"}
    deadline = time.time() + 600
    status = ""
    while time.time() < deadline:
        detail = client.call("GET", f"/submissions/{submission_id}")
        status = detail["status"]
        if status in terminal:
            break
        time.sleep(3)
    if status != "accepted":
        raise RuntimeError(f"验题提交未通过：{status}（submission {submission_id}）")
    client.call("POST", f"/problems/{problem_id}/test-cases/apply")
    client.call("POST", f"/problems/{problem_id}/publish")
    return submission_id


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=os.environ.get("PIGEONOJ_IMPORT_BASE", DEFAULT_BASE))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-verify", action="store_true")
    ap.add_argument("--only", nargs="*", default=[])
    args = ap.parse_args()

    targets = sorted(p for p in PROBLEMS_DIR.glob("*/[01]*") if p.is_dir())
    if args.only:
        targets = [p for p in targets if any(k in f"{p.parent.name}/{p.name}" for k in args.only)]
    if not targets:
        print("没有匹配的题目录", file=sys.stderr)
        return 1

    parsed_all: list[tuple[Path, dict]] = []
    failed_parse: list[str] = []
    for dir_path in targets:
        label = f"{dir_path.parent.name}/{dir_path.name}"
        try:
            parsed = parse_problem(dir_path)
        except ParseError as exc:
            failed_parse.append(f"{label}: {exc}")
            print(f"[解析失败] {label}: {exc}")
            continue
        print(f"[OK] {label}: 「{parsed['title']}」 样例x{len(parsed['samples'])} 测试点x{len(parsed['cases'])}")
        parsed_all.append((dir_path, parsed))
    if failed_parse:
        print(f"\n{len(failed_parse)} 个目录解析失败，中止（先修题面/测试点）", file=sys.stderr)
        return 1
    if args.dry_run:
        return 0

    token = os.environ.get("PIGEONOJ_IMPORT_TOKEN", "")
    if not token:
        print("缺少环境变量 PIGEONOJ_IMPORT_TOKEN", file=sys.stderr)
        return 1
    client = Client(args.base, token)
    existing = client.my_problems()
    print(f"\n线上已有题目 {len(existing)} 道，开始导入（同名复用，重新上传测试点后验题）\n")

    summary: list[str] = []
    for dir_path, parsed in parsed_all:
        label = f"{dir_path.parent.name}/{dir_path.name}"
        try:
            if parsed["title"] in existing:
                pid = existing[parsed["title"]]
                # 复用已有题目：测试点为「生效集不动、暂存集全量替换」语义，
                # 重新走暂存 → 验题 → 晋升 → 发布，覆盖旧错误测试点
                client.call("PUT", f"/problems/{pid}/test-cases", json={"cases": parsed["cases"][:1]})
                if len(parsed["cases"]) > 1:
                    client.call("PATCH", f"/problems/{pid}/test-cases", json={"upserts": parsed["cases"][1:]})
            else:
                data = client.call("POST", "/problems", json={
                    "title": parsed["title"],
                    "background": parsed["background"],
                    "description": parsed["description"],
                    "input_description": parsed["input_description"],
                    "output_description": parsed["output_description"],
                })
                pid = data["id"]
                client.upload_cases(pid, parsed["cases"])
            client.call("PUT", f"/problems/{pid}/samples", json={"samples": parsed["samples"]})
            if args.skip_verify:
                summary.append(f"[草稿] {label}: {pid}（测试点已传，待人工验题发布）")
                print(summary[-1])
                continue
            sid = verify_and_publish(client, pid, parsed)
            summary.append(f"[发布] {label}: {pid}（验题提交 {sid}）")
            print(summary[-1])
        except Exception as exc:  # noqa: BLE001 —— 单题失败不阻断后续导入
            summary.append(f"[失败] {label}: {exc}")
            print(summary[-1], file=sys.stderr)
    print("\n===== 汇总 =====")
    for line in summary:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
