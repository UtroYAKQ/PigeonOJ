/**
 * 团队管理页门控（题单 / 比赛创建、题目引用）：
 * 拉取团队详情并按 my_role 判定 creator / admin；后端仍会强校验。
 */
import { computed, onMounted, ref } from 'vue'

import { ApiError } from '@/api/http'
import { getTeam } from '@/api/teams'
import type { TeamDetail } from '@/types'

export function useTeamAdminGate(teamId: string) {
  const team = ref<TeamDetail | null>(null)
  const loading = ref(true)
  const failed = ref(false)
  /** 2003 = 非团队成员（详情仅成员可见） */
  const forbidden = ref(false)

  const allowed = computed(
    () => team.value?.my_role === 'creator' || team.value?.my_role === 'admin',
  )

  async function load(): Promise<void> {
    loading.value = true
    try {
      team.value = await getTeam(teamId)
      failed.value = false
      forbidden.value = false
    } catch (error) {
      team.value = null
      failed.value = true
      forbidden.value = error instanceof ApiError && error.code === 2003
    } finally {
      loading.value = false
    }
  }

  onMounted(load)

  return { team, loading, failed, forbidden, allowed, load }
}
