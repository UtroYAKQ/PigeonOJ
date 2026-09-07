/**
 * naive 列形状 → Arco a-table 列定义适配。
 * 页面既有 columns 定义（title / key / width / minWidth / render(row, index)）保持不变，
 * 由本函数在绑定处转换，避免组件库迁移期重写各表列配置。
 */
import type { VNodeChild } from 'vue'

export interface WorkbenchColumn {
  title?: string
  key?: string
  width?: number
  minWidth?: number
  align?: 'left' | 'center' | 'right'
  render?: (row: any, index?: number) => VNodeChild
  [extra: string]: unknown
}

type ArcoColumn = {
  title?: string
  dataIndex: string
  width?: number
  minWidth?: number
  align?: 'left' | 'center' | 'right'
  render?: (data: { record: any; rowIndex: number }) => VNodeChild
} & Record<string, unknown>

export function toArcoColumns(columns: WorkbenchColumn[]): ArcoColumn[] {
  return columns.map((col) => {
    const out: ArcoColumn = { dataIndex: String(col.key) }
    const { title, width, minWidth, align, render, key, ...rest } = col
    out.title = title
    if (width !== undefined) out.width = width
    if (minWidth !== undefined) out.minWidth = minWidth
    if (align !== undefined) out.align = align
    Object.assign(out, rest)
    if (render) out.render = ({ record, rowIndex }) => render(record, rowIndex)
    return out
  })
}
