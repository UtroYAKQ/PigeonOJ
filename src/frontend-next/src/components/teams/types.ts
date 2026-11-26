/** 团队模块共享展示组件类型。 */

/** 行内操作菜单项（⋯ 下拉）：key 由宿主解释，label 已本地化 */
export interface RowAction {
  key: string
  label: string
  disabled?: boolean
  destructive?: boolean
}
