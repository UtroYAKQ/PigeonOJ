import { reactive } from 'vue'
import { toast } from 'vue-sonner'

export interface ConfirmOptions {
  title: string
  content?: string
  positiveText?: string
  negativeText?: string
  danger?: boolean
  onPositiveClick?: () => void | Promise<void>
}

interface ConfirmState {
  open: boolean
  options: ConfirmOptions | null
  resolve: ((value: boolean) => void) | null
}

/** 全局确认弹窗状态：由 App.vue 常驻的 ConfirmDialogHost 渲染 */
export const confirmState = reactive<ConfirmState>({
  open: false,
  options: null,
  resolve: null,
})

function settle(value: boolean): void {
  confirmState.resolve?.(value)
  confirmState.resolve = null
  confirmState.open = false
  confirmState.options = null
}

/** 返回 Promise<boolean> 的确认框（新代码优先使用） */
export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  if (confirmState.resolve) settle(false)
  return new Promise<boolean>((resolve) => {
    confirmState.options = options
    confirmState.resolve = resolve
    confirmState.open = true
  })
}

export function closeConfirm(value: boolean): void {
  settle(value)
}

/** 与旧 naive-ui message 对齐的命令式提示（sonner）。 */
export const message = {
  success(text: string): void {
    toast.success(text)
  },
  error(text: string): void {
    toast.error(text)
  },
  warning(text: string): void {
    toast.warning(text)
  },
  info(text: string): void {
    toast.info(text)
  },
  loading(text: string): { destroy: () => void } {
    const id = toast.loading(text, { duration: Infinity })
    return { destroy: () => toast.dismiss(id) }
  },
}

/** 与旧 naive-ui dialog 对齐的兼容层：确认动作异步执行，结果经 onPositiveClick 自行处理。 */
export const dialog = {
  warning(options: ConfirmOptions): void {
    void confirmDialog(options).then((ok) => {
      if (ok) void options.onPositiveClick?.()
    })
  },
  info(options: ConfirmOptions): void {
    void confirmDialog({ ...options, positiveText: options.positiveText ?? 'OK' })
  },
}

/** 确认弹窗 + 异步操作的统一封装（旧调用点保持原签名）。 */
export function confirmAsyncDialog(opts: {
  title: string
  content: string
  positiveText?: string
  action: () => Promise<unknown>
  successMessage?: string | false
  onAfterSuccess?: () => void | Promise<void>
  danger?: boolean
}): void {
  dialog.warning({
    title: opts.title,
    content: opts.content,
    positiveText: opts.positiveText,
    danger: opts.danger,
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
