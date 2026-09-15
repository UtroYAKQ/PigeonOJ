"""LibreOJ（loj.ac）题目爬取：按题号区间抓取题面 / 样例 / 测试点，输出 FPS XML。

产物可直接交给 import_fps_problems.py 导入本地库：
  python -m scripts.crawl_loj --begin 100 --end 101           # 抓取 LOJ 100~101
  python -m scripts.import_fps_problems <仓库根>/loj_problems  # 导入

- LOJ 是「开放数据」OJ，公开题目的测试数据可匿名下载；个别题需要登录时用 --token
  （token = loj.ac 网页登录后 localStorage.appState 里的 token 字段）
- 平台无 SPJ：自定义 checker 的题也照常下载数据并导入，但按测试点比例计分；
  文件输入输出（fileIo）的题自动跳过（PigeonOJ 仅支持 stdin/stdout）
- 默认 1s 间隔礼貌爬取
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "loj_problems"
API = "https://api.loj.ac/api"
USER_AGENT = "pigeonoj-fps-crawler/1.0 (personal study use)"
# 标准比对可接受的 checker 类型（PigeonOJ 无 SPJ，其余类型跳过）
OK_CHECKERS = {"default", "lines", "case_insensitive_lines", "strict"}

HINT_HEADINGS = {"数据范围与提示", "提示", "说明", "数据范围"}
SAMPLE_HEADINGS = {"样例", "样例输入", "样例输出"}


class CrawlError(Exception):
    pass


class LojClient:
    def __init__(self, token: str | None, delay: float):
        self.delay = delay
        self.headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def call(self, path: str, body: dict, retries: int = 3) -> dict:
        last: Exception | None = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(f"{API}/{path}", data=json.dumps(body).encode(),
                                             headers=self.headers, method="POST")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    time.sleep(self.delay)
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:200]
                if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    last = CrawlError(f"HTTP {exc.code}: {detail}")
                    continue
                raise CrawlError(f"HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = exc
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
        raise CrawlError(f"请求失败 {path}: {last}")

    def download(self, url: str, retries: int = 3) -> bytes:
        last: Exception | None = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    return resp.read()
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = exc
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
        raise CrawlError(f"下载失败: {last}")


def cdata(text: str) -> str:
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def section_texts(content: dict) -> tuple[str, str, str, str]:
    """contentSections → (description, input_desc, output_desc, hint)。"""
    description_parts: list[str] = []
    input_desc = ""
    output_desc = ""
    hint_parts: list[str] = []
    for section in content.get("contentSections", []):
        head = (section.get("sectionTitle") or "").strip()
        text = (section.get("text") or "").strip()
        if section.get("type") == "Sample":
            continue  # 用接口返回的真实样例，避免题面重复
        if head in HINT_HEADINGS:
            hint_parts.append(f"### {head}\n\n{text}" if text else head)
        elif head == "输入格式":
            input_desc = text
        elif head == "输出格式":
            output_desc = text
        elif head in SAMPLE_HEADINGS:
            continue
        elif head == "题目描述":
            description_parts.insert(0, text)
        else:
            description_parts.append(f"## {head}\n\n{text}" if head else text)
    return (
        "\n\n".join(p for p in description_parts if p),
        input_desc,
        output_desc,
        "\n\n".join(hint_parts),
    )


def pair_testdata(test_data: list[dict]) -> list[tuple[str, str, str]]:
    """testData 文件清单 → [(stem, in文件名, out文件名)]；.ans 视作输出。"""
    inputs: dict[str, str] = {}
    outputs: dict[str, str] = {}
    for f in test_data:
        name = f.get("filename") or ""
        stem, dot, ext = name.rpartition(".")
        if not dot:
            continue
        ext = ext.lower()
        if ext == "in":
            inputs[stem] = name
        elif ext in ("out", "ans"):
            outputs[stem] = name
    return [(stem, inputs[stem], outputs[stem])
            for stem in sorted(inputs, key=lambda s: (len(s), s)) if stem in outputs]


def build_problem(display_id: int, problem: dict) -> tuple[dict | None, str | None]:
    """整理一题数据；返回 (题目 dict, None) 或 (None, 跳过原因)。"""
    judge = problem.get("judgeInfo") or {}
    if judge.get("fileIo"):
        return None, f"fileIo 文件输入输出，平台仅支持 stdin/stdout"
    if not problem.get("testData"):
        return None, "无测试点数据"

    pairs = pair_testdata(problem["testData"])
    if not pairs:
        return None, "测试点清单无法配对 .in/.out"

    title = problem["localizedContentsOfLocale"]["title"].strip()
    description, input_desc, output_desc, hint = section_texts(problem["localizedContentsOfLocale"])
    samples = [
        {"input": s.get("inputData") or "", "output": s.get("outputData") or ""}
        for s in problem.get("samples") or []
    ]
    samples = [s for s in samples if s["input"] or s["output"]]

    notes: list[str] = []
    if judge.get("subtasks"):
        notes.append(f"原题带子任务绑定（{len(judge['subtasks'])} 组），导入后按测试点比例计分")
    checker = (judge.get("checker") or {}).get("type")
    if checker not in OK_CHECKERS:
        notes.append(f"原题为自定义 checker（{checker}），平台无 SPJ，测试点按标准比对导入")

    return {
        "title": f"LOJ{display_id}. {title}",
        "time_limit_ms": max(1, int(judge.get("timeLimit") or 1000)),
        "memory_limit_mb": max(1, int(judge.get("memoryLimit") or 256)),
        "description": description or title,
        "input_description": input_desc or "无",
        "output_description": output_desc or "无",
        "hint": hint,
        "source": f"LibreOJ #{display_id}（https://loj.ac/p/{display_id}）",
        "samples": samples,
        "pairs": pairs,
        "note": "；".join(notes) or None,
    }, None


def render_fps(problem: dict, stem_pairs: list[tuple[str, str, str]],
               contents: dict[str, bytes]) -> str:
    lines = [
        "  <item>",
        f"<title>{cdata(problem['title'])}</title>",
        f"<time_limit unit=\"ms\">{problem['time_limit_ms']}</time_limit>",
        f"<memory_limit unit=\"mb\">{problem['memory_limit_mb']}</memory_limit>",
        f"<description>{cdata(problem['description'])}</description>",
        f"<input>{cdata(problem['input_description'])}</input>",
        f"<output>{cdata(problem['output_description'])}</output>",
    ]
    for s in problem["samples"]:
        lines.append(f"<sample_input>{cdata(s['input'])}</sample_input>")
        lines.append(f"<sample_output>{cdata(s['output'])}</sample_output>")
    if problem["hint"]:
        lines.append(f"<hint>{cdata(problem['hint'])}</hint>")
    lines.append(f"<source>{cdata(problem['source'])}</source>")
    for stem, in_name, out_name in stem_pairs:
        name = stem or in_name
        lines.append(f"<test_input name=\"{escape(name)}\">"
                     f"{cdata(contents[in_name].decode('utf-8', errors='replace'))}</test_input>")
        lines.append(f"<test_output name=\"{escape(name)}\">"
                     f"{cdata(contents[out_name].decode('utf-8', errors='replace'))}</test_output>")
    lines.append("</item>")
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<fps version=\"1.2\" url=\"https://loj.ac\">\n"
            + "\n".join(lines) + "\n</fps>\n")


def fetch_one(client: LojClient, display_id: int, out_dir: Path) -> tuple[str, str]:
    """抓取单题并写 XML 文件；返回 (状态, 说明)。状态: ok / skip / fail"""
    label = f"LOJ{display_id}"
    try:
        problem = client.call("problem/getProblem", {
            "displayId": display_id,
            "localizedContentsOfLocale": "zh_CN",
            "samples": True,
            "judgeInfo": True,
            "testData": True,
        })
    except CrawlError as exc:
        return "fail", f"{label}: {exc}"
    if problem.get("error"):
        return "skip", f"{label}: {problem['error']}"

    title = problem["localizedContentsOfLocale"]["title"].strip()
    parsed, reason = build_problem(display_id, problem)
    if parsed is None:
        return "skip", f"{label} {title}: {reason}"

    filenames = [fn for _, i, o in parsed["pairs"] for fn in (i, o)]
    try:
        dl = client.call("problem/downloadProblemFiles", {
            "problemId": problem["meta"]["id"],
            "type": "TestData",
            "filenameList": filenames,
        })
    except CrawlError as exc:
        return "fail", f"{label}: 下载数据失败: {exc}"
    if "downloadInfo" not in dl:
        return "skip", f"{label}: 数据无权限（{dl.get('error')}），如已登录可尝试 --token"

    url_map = {d["filename"]: d["downloadUrl"] for d in dl["downloadInfo"]}
    contents: dict[str, bytes] = {}
    for fn in filenames:
        try:
            data = client.download(url_map[fn])
        except CrawlError as exc:
            return "fail", f"{label}: {exc}"
        contents[fn] = data

    xml_text = render_fps(parsed, parsed["pairs"], contents)
    xml_path = out_dir / f"{label}.xml"
    xml_path.write_bytes(xml_text.encode("utf-8"))
    note = f"（{parsed['note']}）" if parsed["note"] else ""
    return "ok", f"{label}: {title} 样例x{len(parsed['samples'])} 测试点x{len(parsed['pairs'])}{note} -> {xml_path.name}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--begin", type=int, help="起始题号")
    src.add_argument("--ids", nargs="*", type=int, help="显式题号列表")
    ap.add_argument("--end", type=int, help="结束题号（含，须与 --begin 同用）")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出目录（默认 <仓库根>/loj_problems）")
    ap.add_argument("--delay", type=float, default=1.0, help="请求间隔秒数（默认 1.0）")
    ap.add_argument("--token", default=None, help="LOJ 会话 token（个别需登录的题用）")
    ap.add_argument("--list-only", action="store_true", help="只列出区间内题目，不抓数据")
    args = ap.parse_args()

    if args.ids is None:
        if args.begin is None or args.end is None:
            ap.error("--ids 或 --begin + --end 必须提供一个")
        if args.end < args.begin:
            ap.error("--end 不能小于 --begin")
        ids = list(range(args.begin, args.end + 1))
    else:
        ids = args.ids

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = LojClient(args.token, args.delay)

    counts = {"ok": 0, "skip": 0, "fail": 0}
    details: dict[str, list[str]] = {"ok": [], "skip": [], "fail": []}
    for display_id in ids:
        status, message = fetch_one(client, display_id, out_dir)
        counts[status] += 1
        details[status].append(message)
        print(("[" + status.upper() + "] " if status != "ok" else "[OK] ") + message,
              file=sys.stderr if status == "fail" else sys.stdout)

    print(f"\n===== 汇总 =====\n成功 {counts['ok']} | 跳过 {counts['skip']} | 失败 {counts['fail']}")
    for message in details["skip"]:
        print("  跳过:", message)
    for message in details["fail"]:
        print("  失败:", message, file=sys.stderr)
    if counts["ok"]:
        print(f"\n下一步：python -m scripts.import_fps_problems {out_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n中断", file=sys.stderr)
        sys.exit(130)
