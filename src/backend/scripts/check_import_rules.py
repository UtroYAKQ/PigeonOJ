"""分层导入规则机械检查（docs/architecture.md 技术分层架构）。

目标结构（对齐 vue-fastapi-admin 风格的按技术层分包）：
    app/api/v1/**       路由层（最上层）
    app/services/**     业务逻辑层（组合仓储完成业务规则）
    app/repositories/** 数据访问仓储层（纯 CRUD + 审计写入助手）
    app/rpc/**          判题网关基础设施（gRPC 服务与作业投递；gen/ 为生成代码）
    app/models/**       ORM 模型
    app/schemas/**      Pydantic 契约模型
    app/enums/**        全局枚举常量（纯净）
    app/core/**         核心设施（database / redis / storage / exceptions / dependency / middlewares / log / init_app）
    app/utils/**        纯工具（安全 / 响应信封 / 分页 / 校验）
    app/settings/**     配置

规则：
1. app.api 仅可被 api 层内部引用；其余任何层 import app.api 即违规（路由层不可被下穿依赖）
2. models / schemas 不得 import services / repositories / rpc（契约层不依赖业务逻辑）
3. enums 保持纯净：不得 import 其他应用分层；utils 不 import api / services / repositories / rpc / models / schemas
4. 豁免（组合根与工具链）：app/core/init_app.py（路由装配）、alembic/**、scripts/**、tests/**

用法：
    python scripts/check_import_rules.py

退出码：0 = 通过；1 = 存在违规（逐条打印）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOTS = (BACKEND_ROOT / "app",)  # 规则只约束应用源码；tests / scripts / alembic 豁免
LAYERS = ("api", "services", "repositories", "rpc", "models", "schemas", "enums", "core", "utils", "settings")
EXEMPT_FILES = {"app.core.init_app"}  # 组合根装配件：允许引用 api 层注册路由


def layer_of(dotted_mod: str) -> str | None:
    """app.<layer>.<...> → <layer>；非应用分层模块返回 None。"""
    parts = dotted_mod.split(".")
    if len(parts) >= 2 and parts[0] == "app" and parts[1] in LAYERS:
        return parts[1]
    return None


def imported_targets(node: ast.AST, pkg: str) -> list[str]:
    """把 import 语句解析成被引用对象的绝对模块路径列表（含相对导入）。"""
    targets: list[str] = []
    if isinstance(node, ast.Import):
        targets.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module is not None:
        base = node.module if node.level == 0 else f"{pkg}.{node.module}"
        targets.append(base)
        for alias in node.names:
            targets.append(f"{base}.{alias.name}")
    return targets


def dotted(path: Path) -> str:
    """文件路径转模块名：a/b/c.py -> a.b.c；a/b/__init__.py -> a.b"""
    rel = path.resolve().relative_to(BACKEND_ROOT).as_posix()
    if rel.endswith("__init__.py"):
        rel = rel[: -len("__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[: -len(".py")]
    return rel.replace("/", ".").rstrip(".")


def package_of(path: Path) -> str:
    mod = dotted(path)
    if path.name == "__init__.py":
        return mod
    return mod.rsplit(".", 1)[0]


def check_file(path: Path) -> list[str]:
    pkg = package_of(path)
    if dotted(path) in EXEMPT_FILES:
        return []
    own_layer = layer_of(pkg)
    problems: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except SyntaxError as exc:
        return [f"{dotted(path)}: 语法错误：{exc}"]

    for node in ast.walk(tree):
        line = getattr(node, "lineno", "?")
        for target in imported_targets(node, pkg):
            target_layer = layer_of(target)
            if target_layer is None or target_layer == own_layer:
                continue
            # 规则 1：路由层只能被自己人 import
            if target_layer == "api":
                problems.append(f"{dotted(path)}:{line}: {own_layer} 层违规依赖路由层 -> {target}")
                continue
            # 规则 2：契约层不依赖业务逻辑
            if own_layer in ("models", "schemas") and target_layer in ("services", "repositories", "rpc"):
                problems.append(f"{dotted(path)}:{line}: {own_layer} 违规依赖业务层 {target_layer} -> {target}")
                continue
            # 规则 3：enums / utils 保持纯净
            if (own_layer == "enums" and target_layer != "enums") or (
                own_layer == "utils" and target_layer in ("api", "services", "repositories", "rpc", "models", "schemas")
            ):
                problems.append(f"{dotted(path)}:{line}: {own_layer} 违规依赖 {target_layer} -> {target}")
    return problems


def main() -> int:
    all_problems: list[str] = []
    files = sorted(p for root in SCAN_ROOTS for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    for path in files:
        all_problems.extend(check_file(path))
    if all_problems:
        print("导入规则检查未通过：")
        for p in all_problems:
            print(" -", p)
        return 1
    print(f"导入规则检查通过（{len(files)} 个文件）：api 不被下穿依赖，契约层与 utils 保持纯净。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
