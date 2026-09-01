import type { RouteLocationNormalizedLoaded } from 'vue-router'

import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** 菜单 / 页面 / 浏览器标题 */
    title?: string
    /** vue-i18n 文案 key，存在时优先用于布局标题 */
    titleKey?: string
    /** 菜单图标名（key 见 @/layout/icon.ts） */
    icon?: string
    /** 是否在侧边栏隐藏（用户设置 / 管理后台由头像菜单进入） */
    hidden?: boolean
    /** 需要的全局角色 code 列表（满足任一即可，见 docs/security.md） */
    roles?: string[]
    /** 是否需要登录 */
    requiresAuth?: boolean
    /** 公开页面（登录 / 注册），跳过登录校验 */
    public?: boolean
    /** 占位页配置（尚未实现的模块页面） */
    placeholder?: {
      title?: string
      titleKey?: string
      description?: string
      descriptionKey?: string
      endpoints?: string[]
    }
    /** 对象上下文页面（详情、创建、提交结果等）；不进入侧边栏菜单 */
    contextPage?: boolean
    /**
     * 面包屑父级工作台：上下文页在面包屑中挂到所属工作台下，
     * 如 管理后台/题目管理/编辑题目（{ titleKey: 'nav.problemsManage', path: '/admin/problems' }）。
     * path 支持按当前路由解析的动态路径（如题单上下文写题页挂到具体题单详情：
     * path: (route) => `/problem-sets/${route.params.setId}`）；
     * 数组形式声明多级父链（按序插入，如 题单/题单详情/题目详情/评测结果）
     */
    breadcrumbParent?:
      | {
          titleKey: string
          path: string | ((route: RouteLocationNormalizedLoaded) => string)
        }
      | Array<{
          titleKey: string
          path: string | ((route: RouteLocationNormalizedLoaded) => string)
        }>
  }
}
