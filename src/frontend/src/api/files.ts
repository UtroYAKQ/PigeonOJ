import { requestUpload } from './http'
import type { UploadResult } from '@/types'

/** 上传当前用户头像；文件类型和大小由后端最终校验。 */
export function uploadAvatar(file: File) {
  const data = new FormData()
  data.append('file', file)
  return requestUpload<UploadResult>('/files/upload/avatar', data)
}

/** 上传 SPJ checker 源码（≤16MB，仅题目管理角色）；返回 MinIO ossId。 */
export function uploadSpj(file: File) {
  const data = new FormData()
  data.append('file', file)
  return requestUpload<{ oss_id: string; content_type: string; size: number }>('/files/upload/spj', data)
}
