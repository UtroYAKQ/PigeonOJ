import type { VNode } from 'vue'

export interface AppTableColumn<T = any> {
  key: string
  title?: string
  width?: string
  align?: 'left' | 'center' | 'right'
  headerClass?: string
  cellClass?: string
  cell?: (row: T, index: number) => VNode | string | number | null
}
