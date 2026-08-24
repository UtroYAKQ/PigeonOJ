import { requestUpload } from './http'
import type { UploadResult } from '@/types'

/** 上传当前用户头像；文件类型和大小由后端最终校验。 */
export function uploadAvatar(file: File) {
  const data = new FormData()
  data.append('file', file)
  return requestUpload<UploadResult>('/files/upload/avatar', data)
}
