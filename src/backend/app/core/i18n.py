"""后端错误消息 i18n：按请求 Accept-Language 在异常处理出口翻译信封 message。

约定（docs/contracts/common.md）：
- 业务代码继续抛中文消息（APIError / 校验器 ValueError），零改动；
- 本模块在全局异常处理器出口查「中文原文 → 英文」目录翻译，未命中原样返回（回退中文）；
- 仅两种语言：zh-CN（默认）/ en-US；错误码 code 不受语言影响。

不引入 gettext / Babel：消息量小（百余条）、无复数与翻译协作流程，
字典方案改动面最小（见 AGENTS.md「不引入新框架」约束）。
"""
from __future__ import annotations

ZH_CN = "zh-CN"
EN_US = "en-US"


def resolve_locale(accept_language: str | None) -> str:
    """解析 Accept-Language 头，返回受支持语言（zh-CN / en-US）。

    按质量值（q，缺省 1.0）降序取第一个 zh* / en* 标签；都不匹配回退 zh-CN。
    形如 "en-US,en;q=0.9,zh-CN;q=0.8"。
    """
    if not accept_language:
        return ZH_CN
    entries: list[tuple[float, str]] = []
    for part in accept_language.split(","):
        piece = part.strip().split(";")
        tag = piece[0].strip().lower()
        if not tag or tag == "*":
            continue
        q = 1.0
        for param in piece[1:]:
            key, _, value = param.strip().partition("=")
            if key.strip().lower() == "q":
                try:
                    q = float(value)
                except ValueError:
                    q = 0.0
        entries.append((q, tag))
    for _q, tag in sorted(entries, key=lambda item: -item[0]):
        if tag.startswith("en"):
            return EN_US
        if tag.startswith("zh"):
            return ZH_CN
    return ZH_CN


# 中文原文 → 英文文案（业务消息全量目录；参数化消息走 _PREFIX_RULES）
_MESSAGES: dict[str, str] = {
    # ---- 通用 / 校验 ----
    "参数不合法": "Invalid parameter",
    "参数格式不正确": "Invalid parameter format",
    "邮箱格式错误": "Invalid email format",
    "密码长度需为 6~72 位": "Password must be 6-72 characters",
    "昵称长度需为 1~64 字符": "Nickname must be 1-64 characters",
    "查询参数不合法": "Invalid query parameter",
    # ---- 认证 / 会话 ----
    "未登录": "Not logged in",
    "用户不存在": "User not found",
    "会话已过期或失效，请重新登录": "Your session has expired, please log in again",
    "会话不存在": "Session not found",
    "不能撤销当前会话": "Cannot revoke the current session",
    "账号状态异常，请联系管理员": "Account status is abnormal, please contact the administrator",
    "无权限": "Forbidden",
    "无权限：需要管理员角色": "Forbidden: administrator role required",
    "无权限：需要管理角色": "Forbidden: manager role required",
    "密码错误": "Wrong password",
    "原密码错误": "Incorrect original password",
    "邮箱或密码错误": "Incorrect email or password",
    "验证码错误": "Incorrect verification code",
    "验证码已过期，请重新获取": "Verification code expired, please request a new one",
    "验证码错误次数过多，请重新获取": "Too many failed verification attempts, please request a new code",
    "请输入邮箱验证码": "Please enter the email verification code",
    "邮件发送失败，请稍后重试": "Failed to send email, please try again later",
    "发送过于频繁，请稍后再试": "Sending too frequently, please try again later",
    "当前站点未开放注册": "Registration is currently disabled",
    "邮箱已注册": "Email already registered",
    "该邮箱已被使用": "This email is already in use",
    "账号已冻结，请联系管理员": "Account is frozen, please contact the administrator",
    "账号已封禁，请联系管理员": "Account is banned, please contact the administrator",
    "账号已注销，请联系管理员": "Account is deleted, please contact the administrator",
    "登录失败次数过多，请稍后再试": "Too many failed login attempts, please try again later",
    "已注销账号不可封禁": "Deleted accounts cannot be banned",
    "已注销账号不可解封": "Deleted accounts cannot be unbanned",
    "已注销账号不可冻结": "Deleted accounts cannot be frozen",
    "已注销账号不可解冻": "Deleted accounts cannot be unfrozen",
    "查看我的题目需要登录": "Log in to view your problems",
    # ---- 用户资料 / 角色 ----
    "个性签名过长（≤255）": "Bio is too long (max 255)",
    "头像仅支持 JPG、PNG、WEBP 或 GIF": "Avatars must be JPG, PNG, WEBP or GIF",
    "头像大小不能超过 2MB": "Avatar must be smaller than 2MB",
    "头像文件不能为空": "Avatar file cannot be empty",
    "头像必须使用当前用户上传的 MinIO 文件或可信外链": "Avatar must be a MinIO file uploaded by you or a trusted external URL",
    "头像地址过长（≤512）": "Avatar URL is too long (max 512)",
    "主题仅支持 light / dark": "Theme only supports light / dark",
    "状态取值不合法": "Invalid status value",
    "角色列表不能为空": "Role list cannot be empty",
    # ---- 文件 ----
    "文件不存在": "File not found",
    "图片仅支持 JPG、PNG、WEBP 或 GIF": "Images must be JPG, PNG, WEBP or GIF",
    "图片大小不能超过 5MB": "Image must be smaller than 5MB",
    "图片文件不能为空": "Image file cannot be empty",
    "文件存储失败，请稍后重试": "Failed to store the file, please try again later",
    # ---- 题目 / 测试点 / 验题 ----
    "题目不存在": "Problem not found",
    "题单不存在": "Problem set not found",
    "无权限管理该题单": "No permission to manage this problem set",
    "无权限：题单不可见": "Forbidden: problem set is not visible to you",
    "题目在题单中重复": "Duplicate problem in the problem set",
    "题目不在该题单中": "Problem not in this problem set",
    # ---- 比赛 ----
    "比赛不存在": "Contest not found",
    "无权限管理该比赛": "No permission to manage this contest",
    "未报名该比赛": "You are not registered for this contest",
    "报名尚未开始": "Registration has not started yet",
    "报名已截止": "Registration is closed",
    "已报名该比赛": "You have already registered",
    "结束时间必须晚于开始时间": "End time must be after start time",
    "报名开始时间不能晚于报名截止时间": "Registration start time cannot be after registration end time",
    "报名截止不能晚于比赛结束": "Registration deadline cannot be after the contest ends",
    "题目不在该比赛中": "Problem not in this contest",
    "比赛尚未开始，题目不可见": "The contest has not started; problems are not visible",
    "比赛尚未开始，不可提交": "The contest has not started; submissions are not allowed",
    "题目未发布或不可见，不可加入比赛": "Problems must be published and visible to be added to a contest",
    "榜单未处于冻结中": "The scoreboard is not frozen",
    "团队比赛随 teams 模块开放": "Team contests will be available with the teams module",
    "题目未发布或不可见，不可加入题单": "Problems must be published and visible to be added to a problem set",
    "团队题单随 teams 模块开放": "Team problem sets will be available with the teams module",
    "团队题单可见性不可修改": "Visibility of team problem sets cannot be changed",
    "题目未发布，不可提交": "Problem is not published; submissions are not allowed",
    "归档题目不可编辑": "Archived problems cannot be edited",
    "归档题目不可编辑测试点": "Test cases of archived problems cannot be edited",
    "归档题目不可编辑样例": "Samples of archived problems cannot be edited",
    "归档题目不可应用测试点": "Test cases of archived problems cannot be applied",
    "已归档题目不可发布": "Archived problems cannot be published",
    "题目已归档": "Problem already archived",
    "题目未验题，不可发布": "Problem must pass verification before publishing",
    "题目无正式测试点，不可发布": "Problem has no official test cases and cannot be published",
    "测试点存在待验证的改动，请重新验题": "Test cases have pending changes, please re-verify",
    "样例在验题通过后被修改，请重新验题": "Samples were modified after verification, please re-verify",
    "对象存储服务未配置或不可用": "Object storage service is not configured or unavailable",
    "测试点输入和输出不能为空": "Test case input and output cannot be empty",
    "测试点输入和输出不能同时为空": "Test case input and output cannot both be empty",
    "测试点上传失败": "Failed to upload test cases",
    "同一测试点被重复更新": "The same test case was updated more than once",
    "测试点不能同时更新和删除": "A test case cannot be both updated and deleted",
    "测试点不存在": "Test case not found",
    "至少保留一个测试点": "Keep at least one test case",
    "没有待生效的测试点改动": "No pending test case changes",
    "测试点尚未通过验题，不能生效": "Test cases have not passed verification and cannot be applied",
    "验题记录不存在": "Verification record not found",
    "无进行中的验题记录": "No in-progress verification record",
    "提交不存在": "Submission not found",
    "邀请链接无效": "Invalid invite link",
    "邀请链接已失效": "Invite link has expired",
    "代码不能超过 64KB": "Code must be smaller than 64KB",
    "提交验题代码时必须指定语言": "Language is required when submitting verification code",
    "测试点内容不能超过 5MB": "Test case content must be smaller than 5MB",
    "样例内容不能超过 64KB": "Sample content must be smaller than 64KB",
    # ---- 标签 ----
    "标签不存在": "Tag not found",
    "标签名已存在": "Tag name already exists",
    "标签已归档": "Tag archived",
    # ---- 管理后台 ----
    "配置项缺少 id": "Config item is missing an id",
    "日志类型不存在": "Log type not found",
    "举报不存在": "Report not found",
    "该举报已处理": "This report has already been handled",
}

# 参数化消息前缀（f-string 拼接动态值）→ 英文前缀，动态段原样保留
_PREFIX_RULES: list[tuple[str, str]] = [
    ("配置不存在：", "Config not found: "),
    ("角色不存在：", "Role does not exist: "),
    ("标签不存在或已归档：", "Tag does not exist or is archived: "),
]


def translate_message(message: str, locale: str) -> str:
    """英文语言下按目录把中文消息翻成英文；命中不了原样返回（回退中文）。"""
    if locale != EN_US or not message:
        return message
    exact = _MESSAGES.get(message)
    if exact:
        return exact
    for zh_prefix, en_prefix in _PREFIX_RULES:
        if message.startswith(zh_prefix):
            return en_prefix + message[len(zh_prefix):]
    return message
