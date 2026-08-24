import { defineStore } from 'pinia'
import { fetchSiteConfig } from '@/api/site'
import { applyTheme } from '@/utils/theme'
import { applyFavicon } from '@/utils/favicon'
import type { SiteConfig } from '@/types'

const COLLAPSE_STORAGE_KEY = 'pigeonoj.sider.collapsed'
const THEME_STORAGE_KEY = 'pigeonoj.theme'

export type ThemeMode = 'light' | 'dark'

/** 站点配置兜底值：后端不可达或字段缺失时保证首屏可用。 */
const DEFAULT_SITE_CONFIG: SiteConfig = {
  name: 'PigeonOJ',
  logo: '',
  icp: '',
  default_theme: 'light',
  register_enabled: true,
  email_verify_enabled: true,
}

function readBool(key: string): boolean {
  try {
    return localStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function readStoredTheme(): string | null {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY)
  } catch {
    return null
  }
}

/**
 * 应用壳 store：侧栏折叠态、主题模式与公开站点配置。
 * 折叠态与显式选择的主题持久化到 localStorage；主题同时驱动 html.dark（Tailwind / Monaco / CSS 变量）。
 * 站点配置来自 GET /site-config：未显式选择主题时应用站点默认主题，名称/Logo/ICP/注册开关驱动壳层展示。
 */
export const useAppStore = defineStore('app', {
  state: () => ({
    collapsed: readBool(COLLAPSE_STORAGE_KEY),
    themeMode: (readStoredTheme() === 'dark' ? 'dark' : 'light') as ThemeMode,
    siteConfig: { ...DEFAULT_SITE_CONFIG },
  }),

  getters: {
    isDark: (state) => state.themeMode === 'dark',
  },

  actions: {
    async loadSiteConfig() {
      try {
        const cfg = await fetchSiteConfig()
        this.siteConfig = { ...DEFAULT_SITE_CONFIG, ...cfg }
        applyFavicon(this.siteConfig.logo)
        // 用户从未显式选过主题时，跟随站点默认主题；只应用不落盘，便于管理员后续切换默认值
        if (readStoredTheme() === null && (cfg.default_theme === 'light' || cfg.default_theme === 'dark')) {
          this.setThemeWithoutPersist(cfg.default_theme)
        }
      } catch {
        /* 拉取失败保持默认值 */
      }
    },
    toggleCollapsed() {
      this.collapsed = !this.collapsed
      try {
        localStorage.setItem(COLLAPSE_STORAGE_KEY, this.collapsed ? '1' : '0')
      } catch {
        /* 忽略 */
      }
    },
    setCollapsed(value: boolean) {
      if (this.collapsed === value) return
      this.toggleCollapsed()
    },
    setTheme(mode: ThemeMode) {
      this.themeMode = mode
      applyTheme(mode)
      try {
        localStorage.setItem(THEME_STORAGE_KEY, mode)
      } catch {
        /* 忽略 */
      }
    },
    setThemeWithoutPersist(mode: ThemeMode) {
      this.themeMode = mode
      applyTheme(mode)
    },
    toggleTheme() {
      this.setTheme(this.isDark ? 'light' : 'dark')
    },
  },
})
