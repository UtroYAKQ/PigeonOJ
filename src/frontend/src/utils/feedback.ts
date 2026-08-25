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

/**
 * 确认弹窗 + 异步操作的统一封装。
 * 消除各视图中重复的 dialog.warning + try/catch/load 样板代码。
 */
export function confirmAsyncDialog(opts: {
  title: string
  content: string
  positiveText?: string
  /** 异步操作（成功后自动调用；失败时弹错误提示） */
  action: () => Promise<any>
  /** 操作成功后的提示文案（传 false 则不提示） */
  successMessage?: string | false
  /** 操作成功后的回调（如刷新列表） */
  onAfterSuccess?: () => void | Promise<void>
}) {
  dialog.warning({
    title: opts.title,
    content: opts.content,
    positiveText: opts.positiveText,
    negativeText: 'Cancel',
    onPositiveClick: async () => {
      try {
        await opts.action()
        if (opts.successMessage !== false) message.success(opts.successMessage ?? 'Success')
        if (opts.onAfterSuccess) await opts.onAfterSuccess()
      } catch (error) {
        message.error(error instanceof Error ? error.message : 'Operation failed')
      }
    },
  })
}
