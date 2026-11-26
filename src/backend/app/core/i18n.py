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


# 中文原文 → 英文文案（业务消息全量目录；参数化消息走 _TEMPLATE_RULES）
_MESSAGES: dict[str, str] = {
    # ---- 通用 / 校验 ----
    "参数不合法": "Invalid parameter",
    "参数格式不正确": "Invalid parameter format",
    "邮箱格式错误": "Invalid email format",
    "密码长度需为 6~72 位": "Password must be 6-72 characters",
    "昵称长度需为 1~64 字符": "Nickname must be 1-64 characters",
    "查询参数不合法": "Invalid query parameter",
    "ids 不能为空": "ids cannot be empty",
    "ids 必须为逗号分隔的题目 UUID": "ids must be a comma-separated list of problem UUIDs",
    "ownership 参数不合法": "Invalid ownership parameter",
    "difficulty_min 不能大于 difficulty_max": "difficulty_min cannot be greater than difficulty_max",
    "全站题目可见性须为 private/public": "Visibility of site-wide problems must be private/public",
    "团队题目可见性仅支持 team_visible / admin_visible": "Team problem visibility only supports team_visible / admin_visible",
    "团队可见性仅可经团队引用设置": "Team visibility can only be set via a team reference",
    "题目可见性不可跨分支修改": "Problem visibility cannot be switched across branches",
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
    "账号已临时冻结，请稍后再试或联系管理员": "Account is temporarily frozen, please try again later or contact the administrator",
    "账号已封禁，请联系管理员": "Account is banned, please contact the administrator",
    "账号已注销，请联系管理员": "Account is deleted, please contact the administrator",
    "登录失败次数过多，请稍后再试": "Too many failed login attempts, please try again later",
    "已注销账号不可封禁": "Deleted accounts cannot be banned",
    "已注销账号不可解封": "Deleted accounts cannot be unbanned",
    "已注销账号不可冻结": "Deleted accounts cannot be frozen",
    "已注销账号不可解冻": "Deleted accounts cannot be unfrozen",
    "查看我的题目需要登录": "Log in to view your problems",
    "查看我的题单需要登录": "Log in to view your problem sets",
    "查看我的团队需要登录": "Log in to view your teams",
    # ---- 用户资料 / 角色 ----
    "个性签名过长（≤255）": "Bio is too long (max 255)",
    "头像仅支持 JPG、PNG、WEBP 或 GIF": "Avatars must be JPG, PNG, WEBP or GIF",
    "头像大小不能超过 2MB": "Avatar must be smaller than 2MB",
    "头像文件不能为空": "Avatar file cannot be empty",
    "头像必须使用当前用户上传的 MinIO 文件或可信外链": "Avatar must be a MinIO file uploaded by you or a trusted external URL",
    "头像必须使用当前用户上传的站内文件 URL 或可信外链": "Avatar must be a site file URL uploaded by you or a trusted external URL",
    "头像地址过长（≤512）": "Avatar URL is too long (max 512)",
    "主题仅支持 light / dark": "Theme only supports light / dark",
    "状态取值不合法": "Invalid status value",
    "角色列表不能为空": "Role list cannot be empty",
    "邮件发件人未配置": "Email sender is not configured",
    "邮件服务未配置，请联系管理员": "Email service is not configured, please contact the administrator",
    # ---- 文件 ----
    "文件不存在": "File not found",
    "图片仅支持 JPG、PNG、WEBP 或 GIF": "Images must be JPG, PNG, WEBP or GIF",
    "图片大小不能超过 5MB": "Image must be smaller than 5MB",
    "图片文件不能为空": "Image file cannot be empty",
    "文件存储失败，请稍后重试": "Failed to store the file, please try again later",
    "上传过于频繁，请稍后再试": "Uploading too frequently, please try again later",
    "图片尺寸或内容无效": "Invalid image dimensions or content",
    "站点 Logo 仅支持 JPG、PNG、WEBP 或 GIF": "Site logo must be JPG, PNG, WEBP or GIF",
    "站点 Logo 大小不能超过 5MB": "Site logo must be smaller than 5MB",
    "站点 Logo 文件不能为空": "Site logo file cannot be empty",
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
    "仅团队成员可报名团队比赛": "Only team members can register for team contests",
    "封榜时间必须晚于开始时间且不晚于结束时间": "Freeze time must be after start time and no later than end time",
    "比赛进行中不可解冻榜单": "The scoreboard cannot be unfrozen while the contest is running",
    "比赛未开始，请使用赛前管理修改时间": "The contest has not started; change times via pre-contest management",
    "新结束时间必须晚于当前结束时间": "New end time must be after the current end time",
    "新结束时间必须晚于当前时刻": "New end time must be later than now",
    "比赛已结束，不可调整封榜时间": "The contest has ended; freeze time cannot be changed",
    "已封榜，不可再调整封榜时间": "The scoreboard is frozen; freeze time cannot be changed",
    "比赛已开始，不可修改结构性信息（公告等赛时调整请使用赛时工具）": "The contest has started; structural information cannot be modified (use live tools for announcements and other in-contest adjustments)",
    "非团队成员，无权查看该比赛": "Not a team member; no permission to view this contest",
    "比赛期间提交记录不可见，结束后开放查看": "Submission records are hidden during the contest and become visible after it ends",
    "未报名该比赛，比赛结束后可查看题目并补题": "You are not registered for this contest; you can view problems and make upsolving submissions after it ends",
    "未报名该比赛，比赛结束后开放补题": "You are not registered for this contest; upsolving opens after it ends",
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
    "测试点内容不能超过 8MB": "Test case content must be smaller than 8MB",
    "样例内容不能超过 64KB": "Sample content must be smaller than 64KB",
    "无权限在该组织创建题目": "No permission to create problems in this organization",
    "无权限创建全站题目": "No permission to create site-wide problems",
    "题目不在该组织题库中": "Problem not in this organization's problem library",
    "题目不在该团队题库中": "Problem not in this team's problem library",
    "题单不在该团队中": "Problem set not in this team",
    "比赛不在该团队中": "Contest not in this team",
    "团队题目不可被引用": "Team problems cannot be referenced",
    "仅可引用已发布题目": "Only published problems can be referenced",
    "仅可引用本组织题库或全站公开题目": "Only problems from this organization's library or public site-wide problems can be referenced",
    "该题目已引用进团队": "This problem is already referenced by the team",
    "无权限查看该题目": "No permission to view this problem",
    "无权限提交该题目": "No permission to submit to this problem",
    "题目未发布": "Problem is not published",
    "题目未配置特判程序": "No special judge is configured for this problem",
    "归档题目不可编辑特判程序": "Special judges of archived problems cannot be edited",
    "特判程序上传失败": "Failed to upload the special judge",
    "特判程序源码不能超过 256KB": "Special judge source must be smaller than 256KB",
    "特判程序存在待验证的改动，请重新验题": "The special judge has pending changes, please re-verify",
    "没有待生效的改动": "No pending changes",
    "暂存改动尚未通过验题，不能生效": "Staged changes have not passed verification and cannot be applied",
    "无权限查看该题目提交": "No permission to view submissions of this problem",
    "语言不在白名单或已禁用": "Language is not whitelisted or is disabled",
    "输入不能超过 64KB": "Input must be smaller than 64KB",
    "样例解释不能超过 64KB": "Sample explanation must be smaller than 64KB",
    "XML 解析失败": "Failed to parse XML",
    "根元素不是 <fps>": "Root element is not <fps>",
    "压缩包超过 64MB 上限": "Archive exceeds the 64MB limit",
    "ZIP 文件解析失败": "Failed to parse the ZIP file",
    "上传内容为空": "Uploaded content is empty",
    "没有解析出任何题目": "No problems were parsed",
    "导出内容超过 256MB 上限，请分批导出": "Export exceeds the 256MB limit, please export in batches",
    # ---- 标签 ----
    "标签不存在": "Tag not found",
    "标签名已存在": "Tag name already exists",
    "标签已归档": "Tag archived",
    # ---- 判题 / 沙箱 ----
    "操作过于频繁，请稍后再试": "Too many operations, please try again later",
    "暂无在线判题节点，请稍后重试": "No judge node is online, please try again later",
    "全局判题并发已达上限，请稍后重试": "Global judging concurrency has reached the limit, please try again later",
    "沙箱执行超时，请稍后重试": "Sandbox execution timed out, please try again later",
    # ---- 组织 ----
    "组织不存在": "Organization not found",
    "组织已解散": "Organization has been dissolved",
    "组织名称已存在": "Organization name already exists",
    "组织至少保留一名管理员": "An organization must keep at least one administrator",
    "组织至少保留一名成员": "An organization must keep at least one member",
    "仅系统管理员可创建组织": "Only system administrators can create organizations",
    "仅系统管理员可解散组织": "Only system administrators can dissolve organizations",
    "仅组织管理员可执行该操作": "Only organization administrators can perform this action",
    "任命的组织管理员不存在或不可用": "The appointed organization administrator does not exist or is unavailable",
    "非组织成员": "Not an organization member",
    "非组织成员，无权查看": "Not an organization member; no permission to view",
    "不能移除自己": "You cannot remove yourself",
    "不能撤销自己的组织管理员身份": "You cannot revoke your own organization administrator role",
    "成员不存在": "Member not found",
    "用户不存在或不可用": "User does not exist or is unavailable",
    # ---- 团队 ----
    "团队不存在": "Team not found",
    "团队已解散": "Team has been dissolved",
    "仅团队创建者可执行该操作": "Only the team creator can perform this action",
    "无权限管理该团队": "No permission to manage this team",
    "非团队成员": "Not a team member",
    "非团队成员，无权查看": "Not a team member; no permission to view",
    "邀请链接无效或已过期": "Invite link is invalid or has expired",
    "已是该团队成员": "Already a member of this team",
    "已有待处理的加入申请": "You already have a pending join request",
    "私有团队仅可通过邀请链接申请加入": "Private teams can only be joined via invite links",
    "申请不存在": "Join request not found",
    "该申请已处理": "This join request has already been handled",
    "创建者无需分配管理员": "The creator does not need to be assigned an administrator role",
    "不能移除自己，请使用退出团队": "You cannot remove yourself; leave the team instead",
    "不能移除团队创建者": "The team creator cannot be removed",
    "创建者不可退出团队，请解散团队": "The creator cannot leave the team; dissolve the team instead",
    # ---- 管理后台 ----
    "配置项缺少 id": "Config item is missing an id",
    "日志类型不存在": "Log type not found",
    "举报不存在": "Report not found",
    "该举报已处理": "This report has already been handled",
}

# 参数化消息模板（f-string 拼接动态值）→ 英文模板：动态段夹在中文前缀与
# 可选中文后缀之间，原样保留；后缀为 None 表示消息到动态段即结束
_TEMPLATE_RULES: list[tuple[str, str, str | None, str | None]] = [
    ("配置不存在：", "Config not found: ", None, None),
    ("角色不存在：", "Role does not exist: ", None, None),
    ("标签不存在或已归档：", "Tag does not exist or is archived: ", None, None),
    ("XML 解析失败: ", "Failed to parse XML: ", None, None),
    ("zip 内没有 .xml/.fps 文件: ", "No .xml/.fps files found in the zip: ", None, None),
    ("单次最多导出 ", "Export up to ", " 题，请分批导出", " problems; export in batches"),
    ("归档题目不可", "Archived problems cannot be ", None, None),
    ("压缩包超过 ", "Archive exceeds ", "MB 上限", "MB limit"),
]


def translate_message(message: str, locale: str) -> str:
    """英文语言下按目录把中文消息翻成英文；命中不了原样返回（回退中文）。"""
    if locale != EN_US or not message:
        return message
    exact = _MESSAGES.get(message)
    if exact:
        return exact
    for zh_prefix, en_prefix, zh_suffix, en_suffix in _TEMPLATE_RULES:
        if not message.startswith(zh_prefix):
            continue
        rest = message[len(zh_prefix):]
        if zh_suffix is None:
            return en_prefix + rest
        if rest.endswith(zh_suffix):
            return en_prefix + rest[: -len(zh_suffix)] + en_suffix
    return message
