"""i18n 消息目录防漂移检查（app/core/i18n.py「中文原文 → 英文」目录）。

机制（app/core/i18n.py）：业务代码抛中文消息，全局异常处理出口按目录翻译，
未命中即原样返回（en-US 请求静默回退中文）。本脚本静态扫描会流经该目录的
异常消息字面量，与目录键集比对，防止新增 / 改动的消息漏登英文翻译。

扫描范围（消息会经 translate_message 翻译的异常）：
- raise APIError(code, message)   全局异常处理器出口（app/core/exceptions.py）
- raise ValueError("…")           Pydantic 校验器 value_error 路径（仅扫 app/schemas）
- raise FpsError("…")             fps 导入错误，经 str(exc) 包装进 APIError

消息形态：
- 纯字面量：必须命中 _MESSAGES 精确键；
- f-string：抽取模板（动态段记为 {}），必须命中 _TEMPLATE_RULES 前后缀，
  且夹在前后缀之间的部分不得残留中文；个别枚举插值的全部取值已按精确键
  登记的，列入 ALLOWED_DYNAMIC_TEMPLATES 白名单；
- 同文件变量 / 关键字实参传文案（如 file.py 的 type_error=…）：做一层常量
  折叠后再按上述规则检查；无法静态解析的列为跳过（打印，不阻断）。

目录读取走 AST 字面量求值（不 import app 包，避免拉起应用依赖）。

用法（从 src/backend 目录运行，同 check_import_rules.py）：
    python scripts/check_i18n_messages.py

退出码：0 = 通过；1 = 存在未登记消息（逐条打印）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOT = BACKEND_ROOT / "app"
I18N_FILE = BACKEND_ROOT / "app" / "core" / "i18n.py"

# 会把 message 送进 i18n 目录的异常 → message 的位置参数下标（或经 message= 关键字）
MESSAGE_ARG_INDEX = {"APIError": 1, "ValueError": 0, "FpsError": 0}
# ValueError 仅在 Pydantic 校验器（schemas）中走 value_error → i18n 路径
VALUE_ERROR_SCAN_ROOTS = ("schemas",)

# 枚举插值模板白名单：动态值的全量取值已按精确键登记在 _MESSAGES
# （services/user.py「已注销账号不可封禁 / 解封 / 冻结 / 解冻」四条）
ALLOWED_DYNAMIC_TEMPLATES = {"已注销账号不可{}"}


def load_catalog(path: Path) -> tuple[set[str], list[tuple[str, str, str | None, str | None]]]:
    """AST 解析 i18n.py，取 _MESSAGES 键集与 _TEMPLATE_RULES（旧名 _PREFIX_RULES 兼容）。"""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    keys: set[str] = set()
    rules: list[tuple[str, str, str | None, str | None]] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not (len(targets) == 1 and isinstance(targets[0], ast.Name)):
            continue
        if targets[0].id == "_MESSAGES":
            keys = set(ast.literal_eval(node.value).keys())
        elif targets[0].id in ("_TEMPLATE_RULES", "_PREFIX_RULES"):
            # 旧版 _PREFIX_RULES 为二元组，补齐到 (前缀, 英文前缀, 中文后缀, 英文后缀)
            normalized = []
            for rule in ast.literal_eval(node.value):
                rule = tuple(rule)
                if len(rule) < 4:
                    rule += (None,) * (4 - len(rule))
                normalized.append(rule)
            rules = normalized
    if not keys:
        raise SystemExit(f"无法从 {path} 解析 _MESSAGES 目录")
    return keys, rules


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def template_of(node: ast.JoinedStr) -> str:
    """f-string → 模板字符串：动态段一律记为 {}（如「已注销账号不可{}」）。"""
    parts = [v.value if isinstance(v, ast.Constant) else "{}" for v in node.values]
    return "".join(parts)


def covered_by_template_rules(template: str, rules: list[tuple]) -> bool:
    """模板是否被某条前后缀规则覆盖，且动态段之外无残留中文。"""
    for zh_prefix, _en_prefix, zh_suffix, _en_suffix in rules:
        if not template.startswith(zh_prefix):
            continue
        rest = template[len(zh_prefix):]
        if zh_suffix is None:
            if not has_cjk(rest):
                return True
        elif rest.endswith(zh_suffix) and not has_cjk(rest[: -len(zh_suffix)]):
            return True
    return False


def collect_aliases(tree: ast.Module) -> dict[str, str]:
    """同文件 `name = "字符串"` 常量折叠表（模块级与函数内一并收集）。"""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases.setdefault(target.id, node.value.value)
    return aliases


def collect_keyword_literals(tree: ast.Module) -> dict[str, list[str]]:
    """同文件所有调用中 `keyword="字符串"` 的取值表（如 file.py 的 type_error=…）。"""
    literals: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    literals.setdefault(kw.arg, []).append(kw.value.value)
    return literals


def message_arg_of(call: ast.Call, index: int) -> ast.expr | None:
    """取异常的消息实参：优先位置参数，兼容 message= 关键字。"""
    if len(call.args) > index:
        return call.args[index]
    for kw in call.keywords:
        if kw.arg == "message":
            return kw.value
    return None


def check_message_value(
    value: ast.expr, rel: str, lineno: int, keys: set[str], rules: list[tuple],
    aliases: dict[str, str], kw_literals: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    """检查单个消息实参，返回 (缺失项, 跳过项)。"""
    missing: list[str] = []
    skipped: list[str] = []

    def check_text(text: str) -> None:
        if text not in keys:
            missing.append(f"{rel}:{lineno}: 缺少登记的英文翻译 -> \"{text}\"")

    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        check_text(value.value)
    elif isinstance(value, ast.JoinedStr):
        template = template_of(value)
        if template in ALLOWED_DYNAMIC_TEMPLATES:
            return missing, skipped
        if covered_by_template_rules(template, rules):
            return missing, skipped
        missing.append(f"{rel}:{lineno}: f-string 模板未登记参数化翻译 -> \"{template}\"")
    elif isinstance(value, ast.Name):
        # 常量折叠：先查同文件赋值，再查同文件关键字实参（type_error=… 这类传参）
        if value.id in aliases:
            check_text(aliases[value.id])
        elif value.id in kw_literals:
            for text in kw_literals[value.id]:
                check_text(text)
        else:
            skipped.append(f"{rel}:{lineno}: 动态消息无法静态解析，跳过 -> {value.id}")
    else:
        skipped.append(f"{rel}:{lineno}: 动态消息（非字面量），跳过")
    return missing, skipped


def main() -> int:
    keys, rules = load_catalog(I18N_FILE)
    problems: list[str] = []
    skipped: list[str] = []
    checked = 0
    files = sorted(p for p in SCAN_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    for path in files:
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError as exc:
            problems.append(f"{rel}: 语法错误：{exc}")
            continue
        aliases = collect_aliases(tree)
        kw_literals = collect_keyword_literals(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in MESSAGE_ARG_INDEX):
                continue
            exc_name = node.func.id
            if exc_name == "ValueError" and not rel.startswith(f"app/{VALUE_ERROR_SCAN_ROOTS[0]}/"):
                continue
            arg = message_arg_of(node, MESSAGE_ARG_INDEX[exc_name])
            if arg is None:
                continue
            checked += 1
            missing, skip = check_message_value(arg, rel, node.lineno, keys, rules, aliases, kw_literals)
            problems.extend(missing)
            skipped.extend(skip)
    for item in skipped:
        print("跳过", item)
    if problems:
        print("i18n 消息目录检查未通过：")
        for item in problems:
            print(" -", item)
        print(f"共 {len(problems)} 条未登记，en-US 请求将回退中文（app/core/i18n.py）。")
        return 1
    print(
        f"i18n 消息目录检查通过（{len(files)} 个文件 / {checked} 条消息，动态跳过 {len(skipped)} 条）："
        "所有流经 i18n 出口的异常消息均已登记英文翻译。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
