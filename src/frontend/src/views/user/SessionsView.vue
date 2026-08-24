<script setup lang="ts">
import { Monitor, Refresh } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import * as usersApi from '@/api/users'
import { dialog, message } from '@/utils/feedback'
import type { UserSession } from '@/types'
import { formatDateTime } from '@/utils/format'

const { t } = useI18n()
const loading = ref(false)
const sessions = ref<UserSession[]>([])
async function load() {
  loading.value = true
  try {
    sessions.value = await usersApi.listSessions()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)
function onRevoke(session: UserSession) {
  dialog.warning({
    title: t('sessions.revokeTitle'),
    content: t('sessions.revokeConfirm', {
      device: session.device_info ?? t('common.unknownDevice'),
    }),
    positiveText: t('action.revoke'),
    negativeText: t('action.cancel'),
    onPositiveClick: async () => {
      try {
        await usersApi.revokeSession(session.id)
        message.success(t('sessions.revoked'))
        await load()
      } catch (e) {
        message.error(e instanceof Error ? e.message : t('common.operationFailed'))
      }
    },
  })
}
</script>

<template>
  <div class="page-stack">
    <n-card :bordered="false">
      <template #header>
        <div class="sessions-head">
          <span>{{ t('sessions.title') }}</span>
          <n-button size="small" secondary :loading="loading" @click="load">
            <template #icon>
              <n-icon :component="Refresh" />
            </template>
            {{ t('action.refresh') }}
          </n-button>
        </div>
      </template>

      <n-list v-if="sessions.length" hoverable clickable>
        <n-list-item v-for="session in sessions" :key="session.id">
          <div class="session-row">
            <div class="session-device">
              <span class="session-device__icon"><n-icon :component="Monitor" /></span>
              <div class="session-device__meta">
                <strong>{{ session.device_info ?? t('common.unknownDevice') }}</strong>
                <small>{{ session.ip_address }}</small>
              </div>
              <n-tag v-if="session.current" size="small" type="success" round>
                {{ t('common.current') }}
              </n-tag>
            </div>
            <div class="session-times">
              <span>{{ t('sessions.lastActive') }}：{{ formatDateTime(session.last_active_at) }}</span>
              <span>{{ t('sessions.loginAt') }}：{{ formatDateTime(session.created_at) }}</span>
              <span>{{ t('sessions.expiresAt') }}：{{ formatDateTime(session.expires_at) }}</span>
            </div>
            <n-button
              text
              type="error"
              :disabled="session.current"
              @click="() => onRevoke(session)"
            >
              {{ session.current ? t('sessions.currentSession') : t('action.revoke') }}
            </n-button>
          </div>
        </n-list-item>
      </n-list>
      <n-spin v-else :show="loading">
        <n-empty :description="t('sessions.empty')" />
      </n-spin>
    </n-card>
  </div>
</template>

<style scoped>
.sessions-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.session-row {
  display: grid;
  grid-template-columns: minmax(200px, 1.2fr) minmax(0, 2fr) auto;
  align-items: center;
  gap: 16px;
  width: 100%;
}
.session-device {
  display: flex;
  align-items: center;
  gap: 10px;
}
.session-device__icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  color: var(--app-primary);
  background: rgba(244, 81, 30, 0.09);
}
.session-device__meta {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.session-device__meta strong {
  font-size: 13px;
}
.session-device__meta small {
  color: var(--app-text-secondary);
  font-size: 11px;
}
.session-times {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
@media (max-width: 860px) {
  .session-row {
    grid-template-columns: 1fr;
  }
}
</style>
