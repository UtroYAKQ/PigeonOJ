"""FPS（freeproblemset，HUSTOJ 题库交换格式）XML 题目导入本地数据库。

CLI 入口：解析 / 入库核心在 app/services/problem_import.py（与
POST /admin/problems/import 管理端点共用，docs/contracts/problems.md「FPS 题库导入」）。
本脚本补充 CLI 特有能力：URL（含 github blob 回退）/ 目录批量扫描 / dry-run。

状态语义（docs/contracts/problems.md）：
- 有测试点且无 SPJ → published 直接可做；无测试点 → draft（待人工补点验题）
- 带 spj：默认跳过；--include-spj 时 checker 源码写暂存集并导入为草稿
  （验题通过后 apply 晋升，不再按标准比对导入）

用法（src/backend 目录，需本地 PG / MinIO 已启动、迁移已执行）：
  python -m scripts.import_fps_problems <fps.xml | fps.zip | URL> ...
  python -m scripts.import_fps_problems --dry-run <url>
  python -m scripts.import_fps_problems --include-spj --owner-email a@b.c <path>

- URL 支持 github.com blob 链接（raw 失败自动回退 api.github.com）
- --dry-run  只解析打印，不写库
- --limit N  本次最多导入 N 题
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import urllib.request
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.problem import Problem
from app.models.user import Role, User, UserRole
from app.services.problem_import import (
    FpsError,
    import_parsed_problems,
    parse_fps,
)

USER_AGENT = "pigeonoj-fps-import/1.0"
HTTP_TIMEOUT = 120


# ---------- 数据获取（CLI 特有；API 端点为上传制无此层） ----------


def github_raw_fallbacks(url: str) -> list[str]:
    """github.com blob 链接 → raw 与 api.github.com 回退列表。"""
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$", url)
    if not m:
        return []
    owner, repo, ref, path = m.groups()
    from urllib.parse import quote
    return [
        f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{quote(path)}",
        f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path)}?ref={ref}",
    ]


def normalize_url(url: str) -> str:
    """URL 路径段 percent-encode（支持含中文的 github blob 链接）。"""
    from urllib.parse import quote, urlsplit, urlunsplit
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"),
                       parts.query, parts.fragment))


def http_get(url: str) -> bytes:
    last_err: Exception | None = None
    fallbacks = github_raw_fallbacks(url)
    # blob 页面本身是 HTML 无用，优先 raw / api 直链；非 github URL 原样请求
    candidates = fallbacks or [url]
    for candidate in candidates:
        try:
            headers = {"User-Agent": USER_AGENT}
            if "api.github.com" in candidate:
                headers["Accept"] = "application/vnd.github.raw"
            req = urllib.request.Request(normalize_url(candidate), headers=headers)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                if resp.status != 200:
                    last_err = FpsError(f"HTTP {resp.status}: {candidate}")
                    continue
                data = resp.read()
            if data.lstrip()[:15].lower().startswith(b"<!doctype html") or \
                    data.lstrip()[:5].lower() == b"<html":
                last_err = FpsError(f"返回 HTML 而非题目数据: {candidate}")
                continue
            return data
        except OSError as exc:
            last_err = exc
    raise FpsError(f"下载失败 {url}: {last_err}")


def extract_if_zip(data: bytes, name: str) -> list[tuple[str, bytes]]:
    from app.services.problem_import import extract_zip_xmls

    if name.lower().endswith(".zip") or data[:2] == b"PK":
        return extract_zip_xmls(data, name)
    return [(name, data)]


def load_source(src: str) -> list[tuple[str, bytes]]:
    """返回 [(名称, xml字节)]；本地文件/目录或 URL，自动识别 zip。

    目录：递归收集 *.xml / *.fps / *.zip（TK 题库批量下载后整目录导入）。
    """
    if re.match(r"^https?://", src):
        data = http_get(src)
        name = src.rsplit("/", 1)[-1].split("?")[0]
        return extract_if_zip(data, name)
    path = Path(src)
    if not path.exists():
        raise FpsError(f"路径不存在: {src}")
    if path.is_dir():
        out = []
        for f in sorted(path.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".xml", ".fps", ".zip"):
                try:
                    out += extract_if_zip(f.read_bytes(), f.name)
                except FpsError as exc:
                    print(f"    ! 跳过 {f.name}: {exc}", file=sys.stderr)
        return out
    return extract_if_zip(path.read_bytes(), path.name)


async def resolve_owner(db, owner_email: str | None) -> User:
    if owner_email:
        user = (await db.execute(select(User).where(User.email == owner_email))).scalar_one_or_none()
        if user is None:
            raise FpsError(f"指定的 --owner-email 用户不存在: {owner_email}")
        return user
    admin = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.code == "admin", UserRole.scope == "global")
            .limit(1)
        )
    ).scalar_one_or_none()
    if admin is None:
        raise FpsError("库中没有全局 admin 用户（先跑 alembic upgrade head + bootstrap）")
    return admin


_STATUS_LABELS = {
    "published": "发布",
    "draft": "草稿（无测试点，待人工补点验题）",
    "draft_spj": "草稿（带特判程序，暂存待验题晋升）",
    "duplicate": "跳过-重复",
    "skipped_spj": "跳过-SPJ",
    "failed": "失败",
}


async def run(args: argparse.Namespace) -> int:
    xml_files: list[tuple[str, bytes]] = []
    for src in args.sources:
        try:
            xml_files += load_source(src)
        except FpsError as exc:
            print(f"[数据源失败] {src}: {exc}", file=sys.stderr)
    if not xml_files:
        print("没有可解析的数据源", file=sys.stderr)
        return 1

    parsed_all: list[dict] = []
    for name, data in xml_files:
        try:
            parsed_all.extend(parse_fps(data))
        except FpsError as exc:
            print(f"[解析失败] {name}: {exc}", file=sys.stderr)
    if not parsed_all:
        print("没有解析出任何题目", file=sys.stderr)
        return 1
    print(f"共解析出 {len(parsed_all)} 道题")

    for parsed in parsed_all:
        print(
            f"  {parsed['title'][:40]} | 时限{parsed['time_limit_ms']}ms "
            f"内存{parsed['memory_limit_mb']}MB | 样例x{len(parsed['samples'])} "
            f"测试点x{len(parsed['tests'])} | spj={'Y' if parsed['has_spj'] else 'N'}"
            f" | 标程x{len(parsed['solutions'])}"
        )
    if args.dry_run:
        return 0

    async with SessionLocal() as db:
        owner = await resolve_owner(db, args.owner_email)
        titles = set((await db.execute(select(Problem.title))).scalars().all())
        outcomes, _truncated = await import_parsed_problems(
            db, owner, parsed_all,
            spj_mode="staged" if args.include_spj else "skip",
            limit=args.limit or 10**9,
            known_titles=titles,
        )
    counts: dict[str, int] = {}
    for outcome in outcomes:
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        print(f"[{_STATUS_LABELS.get(outcome.status, outcome.status)}] {outcome.title}"
              + (f"：{outcome.message}" if outcome.message else ""))
    print("\n===== 汇总 =====")
    for status, label in _STATUS_LABELS.items():
        if counts.get(status):
            print(f"{label} {counts[status]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("sources", nargs="+", help="fps .xml / .zip 本地路径或 URL（支持 github blob 链接）")
    ap.add_argument("--dry-run", action="store_true", help="只解析打印，不写库")
    ap.add_argument("--include-spj", action="store_true", help="导入带 spj 的题（checker 写暂存集并导入为草稿）")
    ap.add_argument("--owner-email", default=None, help="题目归属用户邮箱（缺省取首个全局 admin）")
    ap.add_argument("--limit", type=int, default=None, help="本次最多导入 N 题")
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
