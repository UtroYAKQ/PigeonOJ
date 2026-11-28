/**
 * 文件服务类型（docs/contracts.md §12.3）：上传结果。
 */

export interface UploadResult {
  url: string
  content_type: string
  size: number
}
