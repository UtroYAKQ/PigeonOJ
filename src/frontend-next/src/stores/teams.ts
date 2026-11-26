import { defineStore } from 'pinia'

/**
 * 团队跨页面状态：成员关系变更脏标记。
 * 退出 / 解散团队后回退团队列表时，keepAlive 缓存的列表实例经 onActivated
 * 检查标记并重拉——本人成员关系（我的团队 / 角色标签）必然过期，
 * 不能依赖列表页手动刷新兜底。
 */
export const useTeamsStore = defineStore('teams', {
  state: () => ({
    membershipDirty: false,
  }),
  actions: {
    /** 任何使本人团队成员关系变化的操作（退出 / 解散）后调用 */
    markMembershipChanged() {
      this.membershipDirty = true
    },
    /** 读取并清除标记（团队列表页 onActivated 消费） */
    consumeMembershipDirty(): boolean {
      const dirty = this.membershipDirty
      this.membershipDirty = false
      return dirty
    },
  },
})
