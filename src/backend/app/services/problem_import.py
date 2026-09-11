"""FPS（freeproblemset，HUSTOJ 题库交换格式）题库导入服务。

解析与入库核心，供两个入口共用（docs/contracts/problems.md「FPS 题库导入」）：
- `POST /admin/problems/import`（管理端点，ZIP 上传一键导入，admin 权限）
- `scripts/import_fps_problems.py`（CLI，支持 URL / 目录 / dry-run）

入库语义：
- 解析 fps XML → 逐题建题（题面 / 样例 / 标程留档 → 测试点上传 MinIO → active_case_ids）
- 有测试点且无 SPJ → published（回填 verified_at，种子语义；标题重复按库内现有题跳过）
- 无测试点 → draft
- `<spj>` 携带源码（staged 模式）→ 恒为 draft + 特判程序写暂存集（验题通过后 apply 晋升）
- `<spj>` 仅有标记无源码 → 跳过（无法重建 checker，按标准比对会误判）
- `<difficulty>` 携带 CF 难度分 → 写入 problems.difficulty（NULL 或 >=0；导入/导出双向）
"""
from __future__ import annotations

import base64
import io
import re
import sys
import uuid as uuid_mod
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIError, PARAM_FORMAT_INVALID, RESOURCE_NOT_FOUND
from app.core.storage import S3Error, get_storage
from app.enums import CaseStatus, ProblemStatus, ProblemVisibility
from app.models.problem import Problem, ProblemCounter, TestCase
from app.models.user import User

MAX_CASE_BYTES = 8 * 1024 * 1024
MAX_SAMPLE_BYTES = 64 * 1024
MAX_SOLUTION_BYTES = 256 * 1024
# 特判程序源码上限（与 PUT /problems/{id}/spj 契约一致，docs/contracts/problems.md）
MAX_SPJ_BYTES = 256 * 1024
# 单次请求 / CLI 单轮最多**尝试**的题目数（约束请求时长，超出 truncated 标记；
# 重复 / 跳过 / 失败计入尝试数，超过部分由分批导入处理）
MAX_IMPORT_ATTEMPTS = 20
# 上传压缩包大小上限（0 = 无限制；需同步调整网关 client_max_body_size）
MAX_ARCHIVE_BYTES = 0
# 导出上限：单次最多 20 题（与导入尝试数一致）；原始内容总量护栏（XML 内存构建）
MAX_EXPORT_PROBLEMS = 20
MAX_EXPORT_TOTAL_BYTES = 256 * 1024 * 1024

# 题面图片（docs/contracts/problems.md「FPS 题库导入 / 导出」）：
# 平台只认 Markdown 生态（Hydro 系 fps 导出同款）——图片是题面字段里的
# ![](data:image/...;base64,...)。HTML <img> 形态不识别（原样保留；前端
# markdown-it html:false 下本就不渲染）。
# 导入：解出 base64 → 落 MinIO 导入人 images 空间（files 公开读白名单内，
#       与手工插图同读链路 /api/v1/files/{key}）→ 题面替换为 ![](站内 URL)；
#       单张 >5MB / 非 JPG/PNG/WEBP/GIF / 解码失败 → 占位文本（不保留 base64 噪音）
# 导出：站内插图 URL → 拉回对象存储 → ![](data:image/...;base64,...)（自包含，
#       跨站可迁移）；对象缺失 / 非图片类型保留原样
MAX_INLINE_IMAGE_BYTES = 5 * 1024 * 1024
MAX_INLINE_IMAGES_TOTAL = 20 * 1024 * 1024
_INLINE_IMAGE_TYPES = {"jpeg", "jpg", "png", "gif", "webp"}
_DATA_IMAGE_MD_RE = re.compile(
    r"!\[[^\]]*\]\(\s*data:image/([a-zA-Z0-9.+-]+)(?:;[^;\s\"']*)*;base64,"
    r"([A-Za-z0-9+/=\s]+?)\s*\)"
)
_SITE_IMAGE_MD_RE = re.compile(r"!\[([^\]]*)\]\(/api/v1/files/([^)\s\"']+)\)")
_IMAGE_PLACEHOLDER = "（图片无法迁移：仅支持 JPG / PNG / WEBP / GIF，单张 ≤5MB）"

# HUSTOJ 导出常见未声明 HTML 实体（DTD 之外），统一替换为字面字符
HTML_ENTITIES = {
    "nbsp": "\u00a0", "ldquo": "\u201c", "rdquo": "\u201d", "lsquo": "\u2018",
    "rsquo": "\u2019", "mdash": "\u2014", "ndash": "\u2013", "hellip": "\u2026",
    "copy": "\u00a9", "reg": "\u00ae", "trade": "\u2122", "times": "\u00d7",
    "divide": "\u00f7", "plusmn": "\u00b1", "deg": "\u00b0", "middot": "\u00b7",
    "laquo": "\u00ab", "raquo": "\u00bb",
}
ENTITY_RE = re.compile(r"&(" + "|".join(HTML_ENTITIES) + r");")


class FpsError(Exception):
    pass


@dataclass
class ImportOutcome:
    """单题导入结果（API 响应与 CLI 汇总共用）。"""

    title: str
    status: str  # published / draft / draft_spj / duplicate / skipped_spj / failed
    problem_id: str | None = None
    message: str | None = None


@dataclass
class ImportSummary:
    """一次导入的汇总（total_parsed 含解析失败文件占位项）。"""

    total_parsed: int
    results: list[ImportOutcome] = field(default_factory=list)
    truncated: bool = False

    @property
    def imported(self) -> int:
        return sum(1 for o in self.results if o.status in ("published", "draft", "draft_spj"))


def normalize_entities(data: bytes) -> bytes:
    text = data.decode("utf-8", errors="strict").lstrip("\ufeff")
    return ENTITY_RE.sub(lambda m: HTML_ENTITIES[m.group(1)], text).encode("utf-8")


def text_of(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def parse_limits(node: ET.Element | None, default_unit: str, to_ms: bool) -> int:
    if node is None:
        return 1000 if to_ms else 256
    unit = (node.get("unit") or default_unit).strip().lower()
    try:
        value = float(text_of(node) or "0")
    except ValueError:
        value = 0.0
    if to_ms:
        ms = value * 1000 if unit in ("s", "sec") else value
        return max(1, min(int(round(ms)), 3_600_000))
    mb = value / 1024 if unit in ("kb", "k") else value * 1024 if unit == "gb" else value
    return max(1, min(int(round(mb)), 4096))


def _parse_difficulty(node: ET.Element | None) -> int | None:
    """解析 <difficulty> 元素为非负整数（CF 难度分）；无效值 → None。"""
    if node is None:
        return None
    try:
        val = int(float(text_of(node) or "0"))
    except ValueError:
        return None
    return val if val >= 0 else None


def pair_nodes(inputs: list[ET.Element], outputs: list[ET.Element],
               read, label: str) -> list[dict]:
    """按文档顺序左右配对；双方均带 name 且不一致时警告（仍按顺序配对）。"""
    if len(inputs) != len(outputs):
        print(f"    ! {label}输入/输出数量不一致（{len(inputs)} vs {len(outputs)}），按较少一侧截断",
              file=sys.stderr)
    pairs = []
    for i, (tin, tout) in enumerate(zip(inputs, outputs)):
        in_val, out_val = read(tin)[0], read(tout)[0]
        if not in_val and not out_val:
            print(f"    ! 跳过第 {i + 1} 组{label}：两侧均为空", file=sys.stderr)
            continue
        if len(in_val.encode("utf-8")) > MAX_CASE_BYTES or \
                len(out_val.encode("utf-8")) > MAX_CASE_BYTES:
            print(f"    ! 跳过第 {i + 1} 组{label}：单侧超过 8MB 上限", file=sys.stderr)
            continue
        name = tin.get("name") or tout.get("name") or ""
        if tin.get("name") and tout.get("name") and tin.get("name") != tout.get("name"):
            print(f"    ! 第 {i + 1} 组{label} name 不一致（{tin.get('name')} / {tout.get('name')}）",
                  file=sys.stderr)
        pairs.append({"name": name, "input": in_val, "expected_output": out_val})
    return pairs


def parse_item(item: ET.Element) -> dict:
    title = text_of(item.find("title")) or "未命名题目"
    samples = pair_nodes(item.findall("sample_input"), item.findall("sample_output"),
                         lambda e: (text_of(e),), "样例")
    samples = [
        s for s in samples
        if len(s["input"].encode("utf-8")) <= MAX_SAMPLE_BYTES
        and len(s["expected_output"].encode("utf-8")) <= MAX_SAMPLE_BYTES
    ][:10]
    tests = pair_nodes(item.findall("test_input"), item.findall("test_output"),
                       lambda e: (text_of(e), e.get("name")), "测试点")
    solutions = [
        {"language": s.get("language") or "", "code": text_of(s)}
        for s in item.findall("solution")
    ]
    return {
        "title": title[:255],
        "time_limit_ms": parse_limits(item.find("time_limit"), "s", to_ms=True),
        "memory_limit_mb": parse_limits(item.find("memory_limit"), "mb", to_ms=False),
        "description": text_of(item.find("description")),
        "input_description": text_of(item.find("input")),
        "output_description": text_of(item.find("output")),
        "hint": text_of(item.find("hint")),
        "source": text_of(item.find("source")),
        "has_spj": item.find("spj") is not None,
        # <spj> 元素文本 = 特判程序源码（部分导出器仅作标记，文本为空时无法重建 checker）
        "spj_code": text_of(item.find("spj")),
        "difficulty": _parse_difficulty(item.find("difficulty")),
        "samples": samples,
        "tests": tests,
        "solutions": solutions,
    }


def parse_fps(data: bytes) -> list[dict]:
    """解析 fps XML → 题目 dict 列表；GBK 等编码错报时回退重解码。"""
    try:
        raw = normalize_entities(data)
    except UnicodeDecodeError:
        raw = ENTITY_RE.sub(
            lambda m: HTML_ENTITIES[m.group(1)],
            data.decode("gbk", errors="replace").lstrip("\ufeff"),
        ).encode("utf-8")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FpsError(f"XML 解析失败: {exc}") from exc
    if root.tag != "fps":
        raise FpsError("根元素不是 <fps>")
    return [parse_item(node) for node in root.findall("item")]


def build_solution(solutions: list[dict]) -> str | None:
    blocks = []
    for s in solutions:
        lang = s["language"] or "text"
        blocks.append(f"标程（{lang}）\n\n```{lang.lower()}\n{s['code']}\n```")
    joined = "\n\n".join(blocks)
    if len(joined.encode("utf-8")) > MAX_SOLUTION_BYTES:
        return None
    return joined or None


# ---------- 题面图片双向转换（导入 base64 → 站内插图；导出站内插图 → base64） ----------


def _rebuild_by_spans(text: str, matches: list[re.Match[str]], replacements: list[str]) -> str:
    """按 match span 重建文本（re.sub 不支持异步替换函数）。"""
    parts: list[str] = []
    last = 0
    for match, replacement in zip(matches, replacements, strict=True):
        parts.append(text[last:match.start()])
        parts.append(replacement)
        last = match.end()
    parts.append(text[last:])
    return "".join(parts)


async def convert_import_images(
    storage, owner_id, texts: dict[str, str | None]
) -> tuple[dict[str, str | None], list[str]]:
    """导入侧：题面字段中 Markdown 内嵌图 `![](data:image/...;base64,...)` → 站内插图。

    图片落在导入人 `users/{owner_id}/images/` 空间（files 公开读白名单内）；
    超限 / 格式不支持 / 解码失败替换为占位文本。返回 (转换后字段, 已上传 key 列表)。
    """
    uploaded: list[str] = []
    budget = MAX_INLINE_IMAGES_TOTAL

    async def _handle(match: re.Match[str]) -> str:
        nonlocal budget
        subtype = match.group(1).lower()
        payload = re.sub(r"\s+", "", match.group(2))
        if subtype not in _INLINE_IMAGE_TYPES:
            return _IMAGE_PLACEHOLDER
        try:
            content = base64.b64decode(payload)
        except ValueError:
            return _IMAGE_PLACEHOLDER
        if not content or len(content) > MAX_INLINE_IMAGE_BYTES or len(content) > budget:
            return _IMAGE_PLACEHOLDER
        key = f"users/{owner_id}/images/{uuid_mod.uuid4().hex}"
        await storage.put_bytes(key, content, f"image/{subtype}")
        uploaded.append(key)
        budget -= len(content)
        return f"![](/api/v1/files/{key})"

    converted: dict[str, str | None] = {}
    for name, text in texts.items():
        if text and "data:image" in text:
            matches = list(_DATA_IMAGE_MD_RE.finditer(text))
            if matches:
                replacements = [await _handle(match) for match in matches]
                text = _rebuild_by_spans(text, matches, replacements)
        converted[name] = text
    return converted, uploaded


async def embed_export_images(
    storage, texts: dict[str, str | None]
) -> tuple[dict[str, str | None], int]:
    """导出侧：站内插图 Markdown `![alt](/api/v1/files/key)` → `![alt](data:image/...;base64,...)`。

    仅转换对象存储中真实存在且为 image/* 的引用；缺失 / 非图片保留原样。
    返回 (转换后字段, 转换图片的原始字节数)。
    """

    async def _data_uri(key: str) -> str | None:
        try:
            content, content_type = await storage.get_bytes(key)
        except (OSError, S3Error):
            return None
        if not content or not (content_type or "").startswith("image/"):
            return None
        return f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"

    consumed = 0
    converted: dict[str, str | None] = {}
    for name, text in texts.items():
        if text and "/api/v1/files/" in text:
            matches = list(_SITE_IMAGE_MD_RE.finditer(text))
            if matches:
                replacements: list[str] = []
                for match in matches:
                    alt, key = match.group(1), match.group(2)
                    data_uri = await _data_uri(key)
                    if data_uri is None:
                        replacements.append(match.group(0))
                        continue
                    consumed += (len(data_uri) * 3) // 4  # base64 还原原始大小（护栏口径）
                    replacements.append(f"![{alt}]({data_uri})")
                text = _rebuild_by_spans(text, matches, replacements)
        converted[name] = text
    return converted, consumed


def extract_zip_xmls(data: bytes, name: str) -> list[tuple[str, bytes]]:
    """ZIP → [(归档内路径, xml 字节)]；兼容 cp437 编码的中文文件名。"""
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            try:
                filename = info.filename.encode("cp437").decode("gbk")
            except (UnicodeDecodeError, UnicodeEncodeError):
                filename = info.filename
            if Path(filename).suffix.lower() not in (".xml", ".fps"):
                continue
            out.append((f"{name}/{filename}", zf.read(info)))
    if not out:
        raise FpsError(f"zip 内没有 .xml/.fps 文件: {name}")
    return out


def read_archive(data: bytes, name: str) -> list[tuple[str, bytes]]:
    """上传内容 → [(名称, xml 字节)]；ZIP（按文件名或 PK 魔数识别）或单个 XML。"""
    if MAX_ARCHIVE_BYTES and len(data) > MAX_ARCHIVE_BYTES:
        raise FpsError("压缩包超过 64MB 上限")
    if name.lower().endswith(".zip") or data[:2] == b"PK":
        try:
            return extract_zip_xmls(data, name)
        except zipfile.BadZipFile as exc:
            raise FpsError("ZIP 文件解析失败") from exc
    if not data.lstrip():
        raise FpsError("上传内容为空")
    return [(name or "fps.xml", data)]


async def import_one(db: AsyncSession, storage, owner_id, parsed: dict) -> tuple[str, uuid_mod.UUID]:
    """单题入库；返回 (结果状态, 题目 id)。失败时回滚并清理已上传对象。"""
    tests = parsed["tests"]
    has_checker = bool(parsed["spj_code"].strip())
    # 有测试点且无特判 → published（种子语义）；无测试点 / 带特判 → draft
    status = (
        ProblemStatus.PUBLISHED
        if tests and not parsed["has_spj"]
        else ProblemStatus.DRAFT
    )

    problem = Problem(
        title=parsed["title"],
        background=parsed["source"] or "无",
        description=parsed["description"] or parsed["title"],
        input_description=parsed["input_description"] or "无",
        output_description=parsed["output_description"] or "无",
        note=parsed["hint"] or None,
        solution=build_solution(parsed["solutions"]),
        samples=parsed["samples"],
        active_case_ids=[],
        pending_case_ids=None,
        case_status=CaseStatus.OK if tests else CaseStatus.EMPTY,
        time_limit_ms=parsed["time_limit_ms"],
        memory_limit_mb=parsed["memory_limit_mb"],
        owner_id=owner_id,
        visibility=ProblemVisibility.PUBLIC,
        team_id=None,
        status=status,
        difficulty=parsed["difficulty"],
    )
    if status == ProblemStatus.PUBLISHED:
        now = datetime.now(timezone.utc)
        problem.verified_at = now
        problem.verified_by = owner_id
        problem.published_at = now
        # samples_updated_at 默认随 INSERT 走 DB now()（晚于上面的 app now），
        # 会触发 needs_reverification 的 samples_updated_at > verified_at 误判；
        # 统一钉到同一时刻，保证导入题「已验题」事实成立
        problem.samples_updated_at = now
    db.add(problem)
    await db.flush()
    db.add(ProblemCounter(problem_id=problem.id))

    uploaded: list[str] = []
    # 题面 base64 内嵌图 → 站内插图（落在导入人 images 空间，files 公开读白名单内）；
    # 失败的 key 计入 uploaded，rollback 时一并清理
    converted_fields, image_keys = await convert_import_images(storage, owner_id, {
        "description": parsed["description"],
        "input_description": parsed["input_description"],
        "output_description": parsed["output_description"],
        "hint": parsed["hint"],
        "source": parsed["source"],
    })
    uploaded.extend(image_keys)
    problem.description = converted_fields["description"] or parsed["title"]
    problem.input_description = converted_fields["input_description"] or "无"
    problem.output_description = converted_fields["output_description"] or "无"
    problem.note = converted_fields["hint"] or None
    problem.background = converted_fields["source"] or "无"

    case_ids: list[str] = []
    try:
        if has_checker:
            spj_key = f"problems/{problem.id}/spj/{uuid_mod.uuid4()}/code"
            await storage.put_bytes(spj_key, parsed["spj_code"].encode("utf-8"),
                                    "text/x-c++src; charset=utf-8")
            uploaded.append(spj_key)
            # 特判程序写暂存集：验题通过后 apply 晋升生效（problems.md「SPJ 特判程序」）
            problem.pending_spj_oss_id = spj_key
        for idx, case in enumerate(tests):
            name = (case["name"] or "").strip()
            for suffix in (".in", ".out", ".txt"):
                if name.lower().endswith(suffix):
                    name = name[: -len(suffix)]
            name = (name or f"case{idx + 1:02d}")[:64]
            input_key = f"problems/{problem.id}/cases/{uuid_mod.uuid4()}/input"
            output_key = f"problems/{problem.id}/cases/{uuid_mod.uuid4()}/output"
            await storage.put_bytes(input_key, case["input"].encode("utf-8"),
                                    "text/plain; charset=utf-8")
            await storage.put_bytes(output_key, case["expected_output"].encode("utf-8"),
                                    "text/plain; charset=utf-8")
            uploaded += [input_key, output_key]
            row = TestCase(
                problem_id=problem.id,
                name=name,
                input_oss_id=input_key,
                expected_output_oss_id=output_key,
                sort_order=idx,
            )
            db.add(row)
            await db.flush()
            case_ids.append(str(row.id))
        problem.active_case_ids = case_ids
        await db.commit()
    except Exception:
        await db.rollback()
        for key in uploaded:
            try:
                await storage.delete(key)
            except Exception:  # noqa: S110 —— 清理尽力而为
                pass
        raise
    if has_checker:
        return "draft_spj", problem.id
    return "published" if tests else "draft", problem.id


async def import_parsed_problems(
    db: AsyncSession,
    owner: User,
    items: list[dict],
    *,
    spj_mode: str = "skip",
    limit: int | None = None,
    known_titles: set[str] | None = None,
) -> tuple[list[ImportOutcome], bool]:
    """逐题导入（单题失败不阻断）；返回 (结果列表, 是否截断)。

    limit 约束**尝试数**（含重复 / 跳过 / 失败），为上传端点提供有界请求时长。
    """
    storage = get_storage()
    known = set(known_titles or ())
    if limit is None:
        limit = MAX_IMPORT_ATTEMPTS
    outcomes: list[ImportOutcome] = []
    attempted = 0
    truncated = False
    for parsed in items:
        if attempted >= limit:
            truncated = True
            break
        attempted += 1
        title = parsed["title"]
        if title in known:
            outcomes.append(ImportOutcome(title=title, status="duplicate"))
            continue
        if parsed["has_spj"]:
            if spj_mode == "skip":
                outcomes.append(ImportOutcome(title=title, status="skipped_spj"))
                continue
            if not parsed["spj_code"].strip():
                outcomes.append(ImportOutcome(
                    title=title, status="skipped_spj",
                    message="spj 标记无 checker 源码，无法重建特判程序",
                ))
                continue
            if len(parsed["spj_code"].encode("utf-8")) > MAX_SPJ_BYTES:
                outcomes.append(ImportOutcome(
                    title=title, status="skipped_spj", message="checker 源码超过 256KB 上限",
                ))
                continue
        try:
            status, pid = await import_one(db, storage, owner.id, parsed)
            known.add(title)
            outcomes.append(ImportOutcome(title=title, status=status, problem_id=str(pid)))
        except Exception as exc:  # noqa: BLE001 —— 单题失败不阻断
            outcomes.append(ImportOutcome(title=title, status="failed", message=str(exc)[:200]))
    return outcomes, truncated


class ProblemImportService:
    """FPS 题库导入服务（POST /admin/problems/import；CLI 脚本走模块级函数）。

    FpsError 在本类边界统一转 1001 信封（路由层不感知 services 异常类型）。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def import_archive(self, data: bytes, filename: str, *, owner: User) -> ImportSummary:
        """ZIP / XML 上传 → 解析 → 逐题导入（staged SPJ 模式）。"""
        from app.core.exceptions import APIError, PARAM_FORMAT_INVALID

        try:
            return await self._import(data, filename, owner)
        except FpsError as exc:
            raise APIError(PARAM_FORMAT_INVALID, str(exc), 400) from exc

    async def _import(self, data: bytes, filename: str, owner: User) -> ImportSummary:
        xml_files = read_archive(data, filename)
        results: list[ImportOutcome] = []
        parsed: list[dict] = []
        for name, xml in xml_files:
            try:
                parsed.extend(parse_fps(xml))
            except FpsError as exc:
                results.append(ImportOutcome(title=Path(name).name, status="failed", message=str(exc)))
        if not parsed:
            # 全部解析失败（如上传的单个 XML 非 fps 格式）→ 1001，不返回空成功结果
            if results:
                raise FpsError(results[0].message or "XML 解析失败")
            raise FpsError("没有解析出任何题目")
        titles = set((await self.db.execute(select(Problem.title))).scalars().all())
        outcomes, truncated = await import_parsed_problems(
            self.db, owner, parsed, spj_mode="staged", known_titles=titles,
        )
        return ImportSummary(total_parsed=len(parsed), results=results + outcomes, truncated=truncated)

    async def export_single(self, problem_id: uuid_mod.UUID) -> tuple[bytes, str]:
        """单题导出 → (fps.xml 字节, 附件文件名)；题目不存在 → 3001。"""
        items, missing = await load_export_items(self.db, [problem_id])
        if missing:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        return build_fps_xml(items), f"fps-{str(problem_id)[:8]}.xml"

    async def export_batch(self, problem_ids: list[uuid_mod.UUID]) -> tuple[bytes, str, int]:
        """批量导出 → (zip 字节, 附件文件名, 题数)；ZIP 内含单文件 fps.xml（一题一 item）。

        超过单次上限 → 1001；全部不存在 → 3001；部分存在时跳过缺失项继续导出。
        """
        if len(problem_ids) > MAX_EXPORT_PROBLEMS:
            raise APIError(
                PARAM_FORMAT_INVALID, f"单次最多导出 {MAX_EXPORT_PROBLEMS} 题，请分批导出", 400
            )
        items, _missing = await load_export_items(self.db, problem_ids)
        if not items:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        xml = build_fps_xml(items)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("fps.xml", xml)
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        return buf.getvalue(), f"fps-export-{date}.zip", len(items)


# ---------- 导出（FPS XML 构建，与导入共用格式语义） ----------


@dataclass
class ExportItem:
    """单题导出载荷（生效集数据；build_fps_xml 消费）。"""

    problem_id: uuid_mod.UUID
    title: str
    time_limit_ms: int
    memory_limit_mb: int
    description: str
    input_description: str | None
    output_description: str | None
    note: str | None
    background: str | None
    solution: str | None
    samples: list[dict]
    tests: list[dict]  # [{"name", "input"(bytes), "expected_output"(bytes)}] 按生效集顺序
    spj_code: str | None
    difficulty: int | None = None


async def load_export_items(
    db: AsyncSession, problem_ids: list[uuid_mod.UUID]
) -> tuple[list[ExportItem], list[uuid_mod.UUID]]:
    """读取题目与**生效集**数据 → ExportItem 列表；返回 (可导出项, 未找到的 id)。

    只导出生效内容（active_case_ids / spj_oss_id / samples），暂存未晋升改动不导出。
    """
    storage = get_storage()
    items: list[ExportItem] = []
    missing: list[uuid_mod.UUID] = []
    seen: set[uuid_mod.UUID] = set()
    total_bytes = 0
    for pid in problem_ids:
        if pid in seen:
            continue
        seen.add(pid)
        problem = await db.get(Problem, pid)
        if problem is None:
            missing.append(pid)
            continue
        rows = {
            row.id: row
            for row in (
                await db.execute(select(TestCase).where(TestCase.problem_id == pid))
            ).scalars().all()
        }
        tests: list[dict] = []
        for raw_id in problem.active_case_ids or []:
            try:
                row = rows.get(uuid_mod.UUID(str(raw_id)))
            except ValueError:
                continue
            if row is None:
                continue
            input_bytes, _ = await storage.get_bytes(row.input_oss_id)
            expected_bytes, _ = await storage.get_bytes(row.expected_output_oss_id)
            total_bytes += len(input_bytes) + len(expected_bytes)
            tests.append({
                "name": (row.name or f"case{len(tests) + 1:02d}")[:64],
                "input": input_bytes,
                "expected_output": expected_bytes,
            })
        spj_code = None
        if problem.spj_oss_id:
            raw, _ = await storage.get_bytes(problem.spj_oss_id)
            spj_code = raw.decode("utf-8", errors="replace")
            total_bytes += len(raw)
        # 站内插图 → base64 data URI（自包含 XML，跨站可迁移）；字节数计入总量护栏
        converted_fields, image_bytes = await embed_export_images(storage, {
            "description": problem.description,
            "input_description": problem.input_description,
            "output_description": problem.output_description,
            "note": problem.note,
            "background": problem.background,
        })
        total_bytes += image_bytes
        if total_bytes > MAX_EXPORT_TOTAL_BYTES:
            raise FpsError("导出内容超过 256MB 上限，请分批导出")
        items.append(ExportItem(
            problem_id=problem.id,
            title=problem.title,
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
            description=converted_fields["description"],
            input_description=converted_fields["input_description"],
            output_description=converted_fields["output_description"],
            note=converted_fields["note"],
            background=converted_fields["background"],
            solution=problem.solution,
            samples=[
                {"input": s.get("input") or "", "output": s.get("output") or ""}
                for s in (problem.samples or [])
                if isinstance(s, dict)
            ],
            tests=tests,
            spj_code=spj_code,
            difficulty=problem.difficulty,
        ))
    return items, missing


def build_fps_xml(items: list[ExportItem]) -> bytes:
    """ExportItem 列表 → fps XML 字节（ElementTree 构建，字段自动转义）。

    字段映射与导入反向一致：time_limit unit=ms（导入原样取 ms）、memory_limit unit=mb、
    note → hint、background → source、官方题解 → solution language=markdown、
    生效特判源码 → spj（导入侧按 staged 语义重建）、difficulty → <difficulty>（CF 难度分）。
    """
    fps = ET.Element("fps")
    for it in items:
        item = ET.SubElement(fps, "item")
        ET.SubElement(item, "title").text = it.title
        ET.SubElement(item, "time_limit", {"unit": "ms"}).text = str(it.time_limit_ms)
        ET.SubElement(item, "memory_limit", {"unit": "mb"}).text = str(it.memory_limit_mb)
        ET.SubElement(item, "description").text = it.description
        if it.input_description:
            ET.SubElement(item, "input").text = it.input_description
        if it.output_description:
            ET.SubElement(item, "output").text = it.output_description
        if it.note:
            ET.SubElement(item, "hint").text = it.note
        if it.background and it.background != "无":
            ET.SubElement(item, "source").text = it.background
        for sample in it.samples:
            ET.SubElement(item, "sample_input").text = sample["input"]
            ET.SubElement(item, "sample_output").text = sample["output"]
        for case in it.tests:
            ET.SubElement(item, "test_input", {"name": case["name"]}).text = (
                case["input"].decode("utf-8", errors="replace")
            )
            ET.SubElement(item, "test_output", {"name": case["name"]}).text = (
                case["expected_output"].decode("utf-8", errors="replace")
            )
        if it.solution:
            ET.SubElement(item, "solution", {"language": "markdown"}).text = it.solution
        if it.spj_code:
            ET.SubElement(item, "spj").text = it.spj_code
        if it.difficulty is not None:
            ET.SubElement(item, "difficulty").text = str(it.difficulty)
    return ET.tostring(fps, encoding="utf-8", xml_declaration=True)
