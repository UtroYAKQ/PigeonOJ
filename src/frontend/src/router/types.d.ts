import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** 菜单 / 页面 / 浏览器标题 */
    title?: string
    /** vue-i18n 文案 key，存在时优先用于布局标题 */
    titleKey?: string
    /** 菜单图标名（key 见 @/layout/icon.ts） */
    icon?: string
    /** 是否在侧边栏隐藏（如「用户设置」入口位于底部用户卡） */
    hidden?: boolean
    /** 需要的全局角色 code 列表（满足任一即可，见 docs/architecture.md 权限设计） */
    roles?: string[]
    /** 是否需要登录 */
    requiresAuth?: boolean
    /** 公开页面（登录 / 注册），跳过登录校验 */
    public?: boolean
    /** 区块标题：右侧二级菜单栏左侧标识（如「管理后台」「用户设置」） */
    sectionTitle?: string
    /** 占位页配置（尚未实现的模块页面） */
    placeholder?: { title?: string; titleKey?: string; description?: string; descriptionKey?: string; endpoints?: string[] }
    /** 对象上下文页面（详情、创建、提交结果等）；不进入区块二级导航 */
    contextPage?: boolean
    /** 隐藏区块二级菜单栏（导航已由侧栏承载时使用，如管理后台空间） */
    hideSectionTabs?: boolean
  }
}
