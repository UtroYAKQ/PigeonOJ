import { defineStore } from 'pinia'

// 骨架阶段占位 store：站点级 UI 状态；业务状态随后续各模块各自建 store
export const useAppStore = defineStore('app', {
  state: () => ({
    sidebarCollapsed: false,
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
  },
})
