"""模块导入规则机械检查（docs/architecture.md 分层架构 + 模块通信约定）。

规则：
1. shared/** 不得 import 任何 app.modules.*（Shared 不依赖业务模块）
2. 模块 X 的私有文件不得 import 其他模块 Y 的非 api 文件；
   跨模块只允许 `from app.modules.<Y>.api import ...`（api.py 是唯一出口）
3. 豁免（组合根与工具链）：app/main.py、app/worker.py、alembic/**、scripts/**、tests/**

用法：
    python scripts/check_import_rules.py

退出码：0 = 通过；1 = 存在违规（逐条打印）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = BACKEND_ROOT / "app"
SCAN_ROOTS = (APP_ROOT,)  # 规则只约束应用源码；tests / scripts / alembic 豁免
EXEMPT_FILES = {"app/main.py", "app/worker.py"}


def rel_posix(path: Path) -> str:
    return path.resolve().relative_to(BACKEND_ROOT).as_posix()


def dotted(path: Path) -> str:
    """文件路径转模块名：a/b/c.py -> a.b.c；a/b/__init__.py -> a.b"""
    rel = rel_posix(path)
    if rel.endswith("__init__.py"):
        rel = rel[: -len("__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[: -len(".py")]
    return rel.replace("/", ".").rstrip(".")


def package_of(path: Path) -> str:
    """当前文件所属包的模块名。"""
    mod = dotted(path)
    return mod.rsplit(".", 1)[0] if not rel_posix(path).endswith("__init__.py") else mod


def imported_targets(node: ast.AST, pkg: str) -> list[str]:
    """把 import 语句解析成被引用对象的绝对路径列表（含相对导入与别名）。"""
    targets: list[str] = []
    if isinstance(node, ast.Import):
        targets.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module is not None:
        base = node.module if node.level == 0 else f"{pkg}.{node.module}"
        for alias in node.names:
            targets.append(f"{base}.{alias.name}" if alias.name != "*" else base)
    return targets


def check_file(path: Path) -> list[str]:
    current_pkg = package_of(path)
    in_shared = rel_posix(path).startswith("app/shared/")
    own_module = ".".join(current_pkg.split(".")[:3])  # app.modules.<X>（对 shared 为 app.shared，不适用规则 2）

    problems: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{rel_posix(path)}: 语法错误：{exc}"]

    for node in ast.walk(tree):
        line = getattr(node, "lineno", "?")
        for target in imported_targets(node, current_pkg):
            # 规则 1：shared 不依赖业务模块
            if in_shared and target.startswith("app.modules"):
                problems.append(f"{rel_posix(path)}:{line}: shared 违规依赖业务模块 -> {target}")
                continue
            # 规则 2：模块间只能经对方 api.py
            if target.startswith("app.modules.") and current_pkg.startswith("app.modules."):
                parts = target.split(".")
                target_module = ".".join(parts[:3])
                if target_module == own_module:
                    continue
                if len(parts) >= 4 and parts[3] == "api":
                    continue
                problems.append(f"{rel_posix(path)}:{line}: 跨模块只能 import 对方 api.py -> {target}")
    return problems


def main() -> int:
    all_problems: list[str] = []
    files = sorted(p for root in SCAN_ROOTS for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    for path in files:
        if rel_posix(path) in EXEMPT_FILES:
            continue
        all_problems.extend(check_file(path))
    if all_problems:
        print("导入规则检查未通过：")
        for p in all_problems:
            print(" -", p)
        return 1
    print(f"导入规则检查通过（{len(files)} 个文件）：shared 无业务依赖，模块间仅经 api.py 通信。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
