/**
 * Vitest 全局测试环境垫片（vite.config.ts test.setupFiles）。
 *
 * jsdom 不实现 ResizeObserver；naive-ui 会退到 @juggle/resize-observer 的
 * MutationObserver polyfill，其 Scheduler.stop 在卸载阶段引用的全局
 * removeEventListener 缺失会抛 TypeError 污染测试输出（用例本身通过）。
 * 这里提供 no-op 原生桩，令 polyfill 完全不启动；补挂全局监听函数兜底其余路径。
 */
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

const win = globalThis as unknown as Record<string, unknown>

if (typeof win.ResizeObserver !== 'function') {
  win.ResizeObserver = ResizeObserverStub
}

if (typeof window !== 'undefined') {
  const domWindow = window as unknown as Record<string, unknown>
  for (const name of ['removeEventListener', 'addEventListener', 'dispatchEvent'] as const) {
    if (typeof win[name] !== 'function' && typeof domWindow[name] === 'function') {
      win[name] = domWindow[name]
    }
  }
}
