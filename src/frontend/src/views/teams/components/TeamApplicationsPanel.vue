<script setup lang="ts">
/**
 * 团队详情 · 加入申请面板（管理员）：申请卡片列表与审批（通过 / 拒绝）。
 * 审批成功后除刷新本列表外，还需宿主重拉成员列表与团队概要（emit changed）。
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NEmpty, NSpin } from 'naive-ui'

import { listTeamApplications, reviewTeamApplication } from '@/api/teams'
import { message } from '@/utils/feedback'
import { formatCompact } from '@/utils/format'
import BaseAvatar from '@/components/BaseAvatar.vue'
import type { TeamApplicationItem } from '@/types'

const props = defineProps<{
  teamId: string
  isAdmin: boolean
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const { t } = useI18n()

const applications = ref<TeamApplicationItem[]>([])
const applicationsLoading = ref(false)

async function loadApplications() {
  if (!props.isAdmin) return
  applicationsLoading.value = true
  try {
    const result = await listTeamApplications(props.teamId, { page: 1, page_size: 50 })
    applications.value = result.items
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    applicationsLoading.value = false
  }
}

async function onReview(row: TeamApplicationItem, approve: boolean) {
  try {
    await reviewTeamApplication(props.teamId, row.id, approve)
    message.success(
      t(approve ? 'teams.applications.approveSuccess' : 'teams.applications.rejectSuccess'),
    )
    await loadApplications()
    // 成员列表与团队概要（成员数）已变化：宿主重拉
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

defineExpose({ reload: loadApplications })

onMounted(loadApplications)
</script>

<template>
  <div class="pane-scroll">
    <NSpin :show="applicationsLoading" class="pane-spin">
      <ul v-if="applications.length" class="tile-grid">
        <li v-for="application in applications" :key="application.id" class="tile">
          <BaseAvatar :name="application.nickname" :size="40" />
          <div class="tile__body">
            <div class="tile__head">
              <span class="tile__title" :title="application.nickname">
                {{ application.nickname }}
              </span>
            </div>
            <div class="tile__foot">
              <span class="dot-chip" :class="application.invite_token ? 'dot-chip--admin' : ''">
                <span class="dot-chip__dot" aria-hidden="true" />
                {{
                  application.invite_token
                    ? t('teams.applications.viaInvite')
                    : t('teams.applications.direct')
                }}
              </span>
              <span class="tile__meta">{{ formatCompact(application.applied_at) }}</span>
            </div>
            <div class="tile__actions">
              <NButton size="tiny" type="primary" @click="onReview(application, true)">
                {{ t('teams.applications.approve') }}
              </NButton>
              <NButton size="tiny" quaternary type="error" @click="onReview(application, false)">
                {{ t('teams.applications.reject') }}
              </NButton>
            </div>
          </div>
        </li>
      </ul>
      <NEmpty
        v-else-if="!applicationsLoading"
        :description="t('teams.applications.empty')"
        size="large"
        class="pane-empty"
      />
    </NSpin>
  </div>
</template>

<style scoped>
/* pane 内滚动区：列表撑满，超出滚动 */
.pane-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: grid;
}
.pane-spin {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}
.pane-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
/* 空态：吃满 pane 剩余高度并垂直居中
   （.n-empty 自身已是 flex 列 + align-items: center，补 flex:1 + justify-content 居中） */
.pane-empty {
  flex: 1;
  min-height: 0;
  justify-content: center;
  padding: 56px 0;
}

/* 申请卡片：紧凑小卡片 */
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  list-style: none;
  margin: 0;
  padding: 0 0 4px;
  align-content: start;
}
.tile {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-card-bg, #fff);
  transition: border-color 0.15s ease;
}
.tile:hover {
  border-color: var(--app-text-muted);
}
.tile__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tile__head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.tile__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.35;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tile__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}
.tile__meta {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tile__actions {
  display: flex;
  gap: 6px;
  margin-top: 2px;
}
.dot-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  font-size: 11px;
  line-height: 1;
  color: var(--app-text-secondary);
}
.dot-chip__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--app-text-muted);
}
.dot-chip--admin {
  color: var(--app-info);
}
.dot-chip--admin .dot-chip__dot {
  background: var(--app-info);
}

/* 响应式 */
@media (max-width: 860px) {
  .tile-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
