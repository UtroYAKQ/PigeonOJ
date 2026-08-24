/**
 * 公开站点配置（GET /site-config，未登录可读）。
 * 来源 system_configs 的 site 域白名单字段，见 docs/contracts/admin.md。
 */
export interface SiteConfig {
  /** 站点名称（侧栏 / 登录注册页品牌区） */
  name: string
  /** 站点 Logo：外链 URL；空则回退默认图标（ossId 形态暂不在此消费） */
  logo: string
  /** ICP 备案号；空则不展示 */
  icp: string
  /** 未做主题选择时的站点默认主题 */
  default_theme: 'light' | 'dark'
  /** 是否开放注册（注册页据此禁用表单） */
  register_enabled: boolean
  /** 注册是否需要邮箱验证码（关闭时注册表单不展示验证码输入） */
  email_verify_enabled: boolean
}
