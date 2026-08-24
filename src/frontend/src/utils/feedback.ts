import { computed } from 'vue'
import { createDiscreteApi, darkTheme } from 'naive-ui'
import { themeOverrides } from '@/settings/theme'
import { useAppStore } from '@/stores/app'

/**
 * 全局命令式反馈 API（替代 Element Plus 的 ElMessage / ElMessageBox）。
 * 通过 createDiscreteApi 挂载独立渲染节点，可在组件外（store / api 层）与
 * 组件内统一使用；主题跟随 app store，文案由调用方在触发时用 t() 计算。
 */
const configProviderProps = computed(() => ({
  theme: useAppStore().isDark ? darkTheme : undefined,
  themeOverrides,
}))

export const { message, dialog } = createDiscreteApi(['message', 'dialog'], {
  configProviderProps,
})
