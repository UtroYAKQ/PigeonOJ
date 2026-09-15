"""牛客导出的题库 Excel → PigeonOJ FPS XML 转换脚本。

数据源：牛客「下载题库.xlsx」（编程 sheet，377 题）。
产物：`nk_problems/fps-{batch:03d}.xml`，每个文件 ≤20 题（对齐 OJ 导入单次上限
`MAX_IMPORT_ATTEMPTS`，docs/contracts/problems.md「FPS 题库导入」）。

转换约定：
- 题面统一 Markdown：Niuke 题面是 HTML（公式为 `<img>` 公网图），逐字段转 Markdown；
  公式图（nowcoder.com 的 equation?tex=...）转行内 LaTeX `$...$`，
  普通图片保留为 `![alt](url)` 公网 URL（用户要求「图片为公网 url 可直接用 ![] 使用」）
- 损坏的 MathML `<math>` / KaTeX `<svg>` 是公式图之外重复的残留，直接丢弃，
  公式统一由 equation 图转出的 LaTeX 表达
- 描述字段常把「输入描述 / 输出描述 / 示例」全塞到一个 HTML 里，转前先截断为纯题面
- 测试点从 `测试用例` 列 zip URL 下载解包，按数字前缀配对 .in/.out 写出 test_input/test_output
- 难度分（CF 挡位）来自 `ratings.csv`（题目ID,难度分），未覆盖则按牛客难度列回退映射
  1→800, 2→1000, 3→1300, 4→1800, 5→2200（写进 <difficulty>）

用法：
  python scripts/convert_nk_excel_to_fps.py \
      --xlsx "C:/Users/33112/Downloads/下载题库.xlsx" \
      --out nk_problems [--ratings ratings.csv] [--dump-review nk_review.txt]
"""
from __future__ import annotations

import argparse
import html
import io
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

USER_AGENT = "pigeonoj-nk-fps/1.0"
HTTP_TIMEOUT = 60
MAX_IMPORT_ATTEMPTS = 20
NK_URL = "https://www.nowcoder.com"

_IMG_TAG_RE = re.compile(r"<img\b[^>]*?>", re.I)
_MATHML_RE = re.compile(r"<math\b.*?</math>", re.I | re.S)
_SVG_RE = re.compile(r"<svg\b.*?</svg>", re.I | re.S)
# MathML 内部标签孤儿（<math> 被截断/剥离后残留）：丢弃
_MATHML_ORPHAN_RE = re.compile(
    r"</?(mi|mn|mo|mrow|mfrac|msqrt|mroot|msub|msup|msubsup|munder|mover|munderover|"
    r"mstyle|mpadded|mspace|mtable|mtr|mtd|mtext|merror|mphantom|menclose|semantics|"
    r"annotation|math)\b[^>]*>",
    re.I,
)
_NOBR_RE = re.compile(r"</?nobr\b[^>]*>", re.I)
# Word/Office HTML 命名空间标签（<o:p> 段落标记等）：仅字面标签，无排印语义，直接丢弃
_OFFICE_NS_RE = re.compile(
    r"</?(?:o|w|wx|w10|m|v|sli|wp|mc|a|r|p|tbl|tr|tc|sdt|sdtPr|sdtContent|smart|Custom|xi):"
    r"[a-zA-Z0-9]+\b[^>]*>",
    re.I,
)
_HR_RE = re.compile(r"<hr\b[^>]*/?>", re.I)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.I | re.S)
_BR_RE = re.compile(r"<br\b[^>]*>", re.I)
# HTML 行内标签 → Markdown 平替（无 markdown 等价者保文字）：
# b/strong→**..**、i/em→*..*、s/strike/del→~~..~~、code→`..`、a→[..](href)、u/sub/sup→文字
_PAIR_TAG_RE = re.compile(
    r"<(?P<tag>b|strong|i|em|u|s|strike|del|code|sub|sup|a)\b(?P<attrs>[^>]*)>"
    r"(?P<body>.*?)</(?P=tag)\s*>",
    re.I | re.S,
)
_UNPAIRED_OPEN_RE = re.compile(
    r"<(b|strong|i|em|u|s|strike|del|code|sub|sup|a|font|span)\b[^>]*>", re.I
)
_UNPAIRED_CLOSE_RE = re.compile(
    r"</(b|strong|i|em|u|s|strike|del|code|sub|sup|a|font|span)\s*>", re.I
)
_BLOCK_RE = re.compile(r"</?(p|div|h[1-6]|article|section|blockquote|pre)\b[^>]*>", re.I)
_LI_ITEM_RE = re.compile(r"<li\b[^>]*>(?P<body>.*?)</li\s*>", re.I | re.S)
_LI_OPEN_RE = re.compile(r"<li\b[^>]*>", re.I)
_LI_CLOSE_RE = re.compile(r"</li\s*>", re.I)
_LIST_RE = re.compile(r"</?(ul|ol)\b[^>]*>", re.I)
_TABLE_RE = re.compile(r"<table\b[^>]*>(?P<body>.*?)</table\s*>", re.I | re.S)
_TR_RE = re.compile(r"<tr\b[^>]*>(?P<body>.*?)</tr\s*>", re.I | re.S)
_CELL_RE = re.compile(r"<(td|th)\b[^>]*>(?P<body>.*?)</\1\s*>", re.I | re.S)
_ENTITY_RE = re.compile(r"&(nbsp|lt|gt|amp|quot|apos|le|ge|minus|times|middot|hellip|ldquo|rdquo|lsquo|rsquo|mdash|ndash|copy|deg|plusmn|divide|times|ne|sum|in|mu|nu|lambda|infty|rarr|rarr);", re.I)

_ENTITIES = {
    "nbsp": " ", "lt": "<", "gt": ">", "amp": "&", "quot": '"', "apos": "'",
    "le": "\u2264", "ge": "\u2265", "minus": "\u2212", "times": "\u00d7",
    "middot": "\u00b7", "hellip": "\u2026", "ldquo": "\u201c", "rdquo": "\u201d",
    "lsquo": "\u2018", "rsquo": "\u2019", "mdash": "\u2014", "ndash": "\u2013",
    "copy": "\u00a9", "deg": "\u00b0", "plusmn": "\u00b1", "divide": "\u00f7",
    "ne": "\u2260", "sum": "\u2211", "in": "\u2208", "mu": "\u03bc", "nu": "\u03bd",
    "lambda": "\u03bb", "infty": "\u221e", "rarr": "\u2192",
}


def decode_entities(text: str) -> str:
    text = _ENTITY_RE.sub(lambda m: _ENTITIES.get(m.group(1).lower(), m.group(0)), text)
    return html.unescape(text)


def _tex_value(src: str) -> str | None:
    """从公式图 URL 里取 tex 参数并 URL 解码；非公式图返回 None。"""
    m = re.search(r"(?:www|hr)\.nowcoder\.com/equation\?([^#]+)", src, re.I)
    if not m:
        return None
    val = re.search(r"(?:^|&)tex=([^&]+)", m.group(1))
    if not val:
        return None
    # 用 unquote（非 unquote_plus）：保留 LaTeX 里的字面 '+'
    return urllib.parse.unquote(val.group(1))


def _img_to_markdown(tag: str) -> str:
    """单个 <img>：公式图 → $LaTeX$，普通图 → ![alt](src)。"""
    src_m = re.search(r'\bsrc="([^"]*)"', tag, re.I)
    src = html.unescape(src_m.group(1)) if src_m else ""
    alt_m = re.search(r'\balt="([^"]*)"', tag, re.I)
    alt = alt_m.group(1) if alt_m else ""
    tex = _tex_value(src)
    if tex is not None:
        return f"${tex}$"
    return f"![{alt or ''}]({src})"


def replace_images(text: str) -> str:
    """<img> → 公式图转 $LaTeX$；其余图保留公网 URL => ![alt](src)。"""
    return _IMG_TAG_RE.sub(lambda m: _img_to_markdown(m.group(0)), text)


def _pair_to_md(match: re.Match[str]) -> str:
    """单个配对标签 → Markdown 平替（u/sub/sup 无等价格式，保文字）。"""
    tag = match.group("tag").lower()
    body = match.group("body")
    if tag in ("b", "strong"):
        return f"**{body}**"
    if tag in ("i", "em"):
        return f"*{body}*"
    if tag in ("s", "strike", "del"):
        return f"~~{body}~~"
    if tag == "code":
        return f"`{body}`"
    if tag == "a":
        href = re.search(r'\bhref="([^"]*)"', match.group("attrs"))
        if href:
            return f"[{body}]({href.group(1)})"
        return body
    return body


def _apply_pair_tags(text: str) -> str:
    """迭代替换配对标签直到稳定（支持嵌套，如 <b><i>..</i></b>）。"""
    for _ in range(10):
        new = _PAIR_TAG_RE.sub(_pair_to_md, text)
        if new == text:
            break
        text = new
    return text


def _table_to_md(match: re.Match[str]) -> str:
    """<table> → GFM 表格（首行作表头；n 列对齐分隔行）。"""
    rows = []
    for tr in _TR_RE.finditer(match.group("body")):
        cells = [
            re.sub(r"[ \t\r\n\u3000]+", " ", c.group("body")).strip()
            for c in _CELL_RE.finditer(tr.group("body"))
        ]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    out: list[str] = []
    for i, row in enumerate(rows, 1):
        row = row + [""] * (ncols - len(row))
        out.append("| " + " | ".join(row) + " |")
        if i == 1:
            out.append("|" + " --- |" * ncols)
    return "\n\n" + "\n".join(out) + "\n\n"


def html_to_markdown(html_text: str | None) -> str | None:
    """Niuke 题面 HTML → Markdown（公式图转 LaTeX，标签转 Markdown 平替）。"""
    if html_text is None:
        return None
    text = html_text
    # 注释 / 损坏的 MathML / KaTeX SVG 残留：与公式图重复，直接丢弃
    text = _COMMENT_RE.sub("", text)
    text = _MATHML_RE.sub("", text)
    text = _SVG_RE.sub("", text)
    text = _MATHML_ORPHAN_RE.sub("", text)
    text = _NOBR_RE.sub("", text)
    text = _OFFICE_NS_RE.sub("", text)
    text = replace_images(text)
    # 先还原实体再清标签：牛客导出常见 &lt;b&gt; 等转义形态，须先还原才能识别标签
    text = decode_entities(text)
    text = _TABLE_RE.sub(_table_to_md, text)
    text = _LI_ITEM_RE.sub(lambda m: "\n- " + m.group("body").strip() + "\n", text)
    # 未闭合 <li>（HTML 允许无 </li>）：补成列表项占位后再清残余
    text = _LI_OPEN_RE.sub("\n- ", text)
    text = _LI_CLOSE_RE.sub("\n", text)
    text = _LIST_RE.sub("\n", text)
    text = _BLOCK_RE.sub("\n", text)
    text = _apply_pair_tags(text)
    text = _UNPAIRED_OPEN_RE.sub("", text)
    text = _UNPAIRED_CLOSE_RE.sub("", text)
    # <br> → Markdown 硬换行（两个尾随空格 + 换行；markdown-it breaks:false 下唯此有换行效果）
    text = _BR_RE.sub("  \n", text)
    # <hr> → Markdown 分隔线
    text = _HR_RE.sub("\n\n---\n\n", text)
    # 归一化空白：行内连续空白折叠为单空格；空行保留为段落分隔；硬换行星保留尾随双空格
    lines = []
    blank = 0
    for raw_line in text.split("\n"):
        hard_break = raw_line.endswith("  ")
        line = re.sub(r"[ \t\u3000]+", " ", raw_line.replace("\xa0", " ")).strip()
        if hard_break:
            lines.append((line + "  ") if line else "")
            blank = 0
            continue
        if not line:
            blank += 1
            continue
        if blank:
            lines.append("")
        lines.append(line)
        blank = 0
    md = "\n".join(lines).strip()
    return md or None


def cut_merged_statement(desc: str) -> str:
    """描述列常把 输入描述/输出描述/示例 塞在同一段 HTML，截到第一个标记之前。"""
    markers = ("输入描述", "输出描述", "示例", "输入：", "输出：")
    best = len(desc)
    for mk in markers:
        idx = desc.find(mk)
        if idx != -1:
            best = min(best, idx)
    return desc[:best]


def download(url: str, retries: int = 3) -> bytes:
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                if resp.status == 200:
                    return resp.read()
                last_err = RuntimeError(f"HTTP {resp.status}")
        except Exception as exc:  # noqa: BLE001 —— 重试由调用方吞掉
            last_err = exc
    raise RuntimeError(f"下载失败 {url}: {last_err}")


def parse_test_zip(data: bytes) -> list[tuple[str, str]]:
    """zip → [(input, output)]，按数字前缀配对的 .in/.out，数字升序。"""
    pairs: dict[int, dict[str, str]] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            m = re.match(r"^(\d+)(\.(in|out|input|output|txt))$", name, re.I)
            if not m:
                continue
            num = int(m.group(1))
            suffix = m.group(3).lower()
            content = zf.read(info).decode("utf-8", errors="replace").strip("\ufeff")
            d = pairs.setdefault(num, {})
            if suffix in ("in", "input") and "in" not in d:
                d["in"] = content
            elif suffix in ("out", "output") and "out" not in d:
                d["out"] = content
    result = []
    for num in sorted(pairs):
        d = pairs[num]
        if "in" in d and "out" in d:
            result.append((d["in"].rstrip("\n") + "\n", d["out"].rstrip("\n") + "\n"))
    return result


def rating_fallback(nk_difficulty) -> int:
    return {1: 800, 2: 1000, 3: 1300, 4: 1800, 5: 2200}.get(int(nk_difficulty or 2), 1000)


def load_ratings(path: Path | None) -> dict[int, int]:
    out: dict[int, int] = {}
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "," not in line:
                continue
            pid_s, rating_s = line.split(",", 1)
            try:
                out[int(float(pid_s))] = int(rating_s.strip())
            except ValueError:
                continue
    return out


def build_fps(root: ET.Element, problems: list[dict]) -> None:
    for p in problems:
        item = ET.SubElement(root, "item")
        ET.SubElement(item, "title").text = p["title"]
        ET.SubElement(item, "time_limit", {"unit": "ms"}).text = str(p["time_limit_ms"])
        ET.SubElement(item, "memory_limit", {"unit": "mb"}).text = str(p["memory_limit_mb"])
        ET.SubElement(item, "description").text = p["description"]
        if p["input"]:
            ET.SubElement(item, "input").text = p["input"]
        if p["output"]:
            ET.SubElement(item, "output").text = p["output"]
        if p["hint"]:
            ET.SubElement(item, "hint").text = p["hint"]
        if p["source"]:
            ET.SubElement(item, "source").text = p["source"]
        ET.SubElement(item, "difficulty").text = str(p["difficulty"])
        for sample_in, sample_out in p["samples"]:
            ET.SubElement(item, "sample_input").text = sample_in
            ET.SubElement(item, "sample_output").text = sample_out
        for name, tin, tout in p["tests"]:
            ET.SubElement(item, "test_input", {"name": name}).text = tin
            ET.SubElement(item, "test_output", {"name": name}).text = tout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xlsx", default=r"C:\Users\33112\Downloads\下载题库.xlsx")
    ap.add_argument("--out", default="nk_problems")
    ap.add_argument("--ratings", default=None, help="题目ID,难度分 CSV；未覆盖按牛客难度回退")
    ap.add_argument("--dump-review", default=None, help="导出 nk_review.txt 评审清单路径")
    ap.add_argument("--max-downloads", type=int, default=0,
                    help="限制测试点下载题数（0=全部；调试用）")
    ap.add_argument("--skip-download", action="store_true", help="不下载测试点，仅样例入 FPS")
    args = ap.parse_args()

    import openpyxl
    wb = openpyxl.load_workbook(args.xlsx)
    ws = wb["编程"]
    ratings = load_ratings(Path(args.ratings) if args.ratings else None)

    problems: list[dict] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        title = str(row[0]).strip() if row[0] else None
        if not title:
            continue
        pid = int(float(row[1]))
        description = html_to_markdown(cut_merged_statement(row[16] or "")) or title
        input_desc = html_to_markdown(row[17]) or "无"
        output_desc = html_to_markdown(row[18]) or "无"
        hint = html_to_markdown(row[19]) if row[19] else None
        test_zip_url = row[20] if isinstance(row[20], str) and row[20].strip() else None
        samples = []
        for si, so, expl in zip(row[21::3], row[22::3], row[23::3]):
            if not si and not so:
                break
            samples.append((str(si), str(so)))
        problems.append({
            "id": pid,
            "title": title,
            "time_limit_ms": int(round(float(row[13] or 1.0) * 1000)),
            "memory_limit_mb": int(float(row[14] or 256)),
            "description": description,
            "input": input_desc,
            "output": output_desc,
            "hint": hint,
            "source": f"牛客 {title}（题目ID {pid}，https://www.nowcoder.com）",
            "difficulty": ratings.get(pid, rating_fallback(row[2])),
            "tests": [],
            "samples": samples,
            "test_zip_url": test_zip_url,
            "nk_difficulty": row[2],
        })

    if args.dump_review:
        with open(args.dump_review, "w", encoding="utf-8") as f:
            for p in problems:
                f.write(f"=== ID {p['id']} | {p['title']} | 牛客难度 {p['nk_difficulty']}"
                        f" | CF {p['difficulty']}\n")
                f.write(p["description"] + "\n")
                if p["input"]:
                    f.write(f"[输入] {p['input']}\n")
                if p["output"]:
                    f.write(f"[输出] {p['output']}\n")
                f.write("\n")
        print(f"评审清单已写出: {args.dump_review}（{len(problems)} 题）")
        return 0

    n_dl = 0
    for idx, p in enumerate(problems):
        if args.skip_download or not p["test_zip_url"]:
            continue
        if args.max_downloads and n_dl >= args.max_downloads:
            print(f"  已达 --max-downloads={args.max_downloads}，余下不下载", file=sys.stderr)
            break
        try:
            data = download(p["test_zip_url"])
            pairs = parse_test_zip(data)
            if not pairs:
                print(f"  ! {p['id']} {p['title']}: zip 无可用 in/out 对", file=sys.stderr)
                continue
            p["tests"] = [
                (f"case{n}", tin, tout) for n, (tin, tout) in enumerate(pairs, 1)
            ]
            n_dl += 1
        except Exception as exc:  # noqa: BLE001 —— 单题下载失败不阻断
            print(f"  ! {p['id']} {p['title']}: {exc}", file=sys.stderr)
        if (idx + 1) % 50 == 0:
            print(f"  进度 {idx + 1}/{len(problems)}（已下载测试点 {n_dl} 题）", file=sys.stderr)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    # 先写一个内含全部题目的总 fps.xml（≤20 每文件的 cut 版）
    batches = [problems[i:i + MAX_IMPORT_ATTEMPTS]
               for i in range(0, len(problems), MAX_IMPORT_ATTEMPTS)]
    files_written = []
    for n, batch in enumerate(batches, 1):
        root = ET.Element("fps", {"version": "1.2", "url": NK_URL})
        build_fps(root, batch)
        xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        file_path = out_dir / f"fps-{n:03d}.xml"
        file_path.write_bytes(xml_bytes)
        files_written.append(str(file_path))

    with_test = sum(1 for p in problems if p["tests"])
    print(f"完成：{len(problems)} 题 -> {len(files_written)} 个 FPS 文件于 {args.out}")
    print(f"含测试点 {with_test} 题 / 仅样例 {len(problems) - with_test} 题")
    return 0


if __name__ == "__main__":
    sys.exit(main())