/** 剪贴板写入：成功返回 true；失败不抛出，由调用方决定提示方式 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
