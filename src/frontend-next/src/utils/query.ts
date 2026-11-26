/**
 * 构建 URL 查询字符串：跳过 null/undefined/空字符串/false 值。
 * 消除各 API 文件中重复的 URLSearchParams 手动拼接。
 */
export function buildQuery(params: Record<string, any> | undefined): string {
  if (!params) return ''
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== '' && v !== false) usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}
