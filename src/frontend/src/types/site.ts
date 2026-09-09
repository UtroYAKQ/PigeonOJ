/**
 * 公开站点配置（GET /site-config，未登录可读）。
 * 来源 system_configs 的 site 域白名单字段，见 docs/contracts/admin.md。
 */

/** 首页轮播海报项（site.banners 配置元素；image 必填，title / link 可选） */
export interface SiteBanner {
  image: string
  title: string
  link: string
}

export interface SiteConfig {
  /** 站点名称（侧栏 / 登录注册页品牌区） */
  name: string
  /** 站点 Logo：外链 URL 或站内文件 URL（/api/v1/files/site/logo/…，经 /files/upload/site-logo 上传）；空则回退默认图标 */
  logo: string
  /** ICP 备案号；空则不展示 */
  icp: string
  /** 未做主题选择时的站点默认主题 */
  default_theme: 'light' | 'dark'
  /** 是否开放注册（注册页据此禁用表单） */
  register_enabled: boolean
  /** 注册是否需要邮箱验证码（关闭时注册表单不展示验证码输入） */
  email_verify_enabled: boolean
  /** 首页轮播海报（site.banners；空数组 = 不渲染轮播区，回退品牌横幅） */
  banners: SiteBanner[]
  /** 首页系统公告（site.announcement；Markdown 文本，经 MarkdownView 渲染；空串 = 不展示） */
  announcement: string
}
