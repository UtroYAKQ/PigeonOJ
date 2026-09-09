<script setup lang="ts">
/**
 * 会话管理（/user/sessions）：活跃设备列表 + 在线态 + 精准下线。
 * 在线判定随服务端（5 分钟内有活动）；同设备重复登录由后端去重（登录替换旧会话）。
 */
import { Cellphone, Monitor, Platform } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import * as usersApi from '@/api/users'
import RefreshButton from '@/components/RefreshButton.vue'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import type { UserSession } from '@/types'
import { formatDateTime } from '@/utils/format'

const { t } = useI18n()
const loading = ref(false)
const revokingOthers = ref(false)
const sessions = ref<UserSession[]>([])

const othersCount = computed(() => sessions.value.filter((s) => !s.current).length)
const onlineCount = computed(() => sessions.value.filter((s) => s.online).length)

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
  confirmAsyncDialog({
    title: t('sessions.revokeTitle'),
    content: t('sessions.revokeConfirm', {
      device: session.device_info ?? t('common.unknownDevice'),
    }),
    positiveText: t('action.revoke'),
    action: () => usersApi.revokeSession(session.id),
    successMessage: t('sessions.revoked'),
    onAfterSuccess: () => load(),
  })
}

function onRevokeOthers() {
  confirmAsyncDialog({
    title: t('sessions.revokeOthersTitle'),
    content: t('sessions.revokeOthersConfirm', { count: othersCount.value }),
    positiveText: t('sessions.revokeOthers'),
    action: async () => {
      revokingOthers.value = true
      try {
        await usersApi.revokeOtherSessions()
      } finally {
        revokingOthers.value = false
      }
    },
    successMessage: t('sessions.revokedOthers', { count: othersCount.value }),
    onAfterSuccess: () => load(),
  })
}

/** 设备形态图标：mobile / tablet / desktop（依据 device_info 关键词，缺省显示器） */
function deviceIcon(session: UserSession) {
  const info = (session.device_info ?? '') + (session.user_agent ?? '')
  if (/移动端|mobile|iPhone|Android/i.test(info)) return Cellphone
  if (/平板|tablet|iPad/i.test(info)) return Platform
  return Monitor
}
</script>

<template>
  <div class="page-stack">
    <n-card :bordered="false">
      <template #header>
        <div class="sessions-head">
          <span>{{ t('sessions.title') }}</span>
          <div class="sessions-head__actions">
            <n-button
              v-if="othersCount > 0"
              size="small"
              type="warning"
              secondary
              :loading="revokingOthers"
              @click="onRevokeOthers"
            >
              {{ t('sessions.revokeOthers') }}（{{ othersCount }}）
            </n-button>
            <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
          </div>
        </div>
      </template>

      <!-- 空态样板（frontend.md）：列表与空态 v-show 互斥（v-if 分支会在空态时卸载整个列表），
           空态用全局 table-fill-empty 拉伸居中 -->
      <n-spin :show="loading">
        <n-list v-show="sessions.length" hoverable clickable>
          <n-list-item v-for="session in sessions" :key="session.id">
            <div class="session-row" :class="{ 'session-row--stale': !session.online }">
              <div class="session-device">
                <span class="session-device__icon">
                  <n-icon :component="deviceIcon(session)" />
                </span>
                <div class="session-device__meta">
                  <strong>{{ session.device_info ?? t('common.unknownDevice') }}</strong>
                  <small>
                    {{ session.ip_address ?? '--' }}
                    <template v-if="session.location"> · {{ session.location }}</template>
                  </small>
                </div>
                <n-tag v-if="session.current" size="small" type="success" round>
                  {{ t('common.current') }}
                </n-tag>
                <n-tag
                  v-else-if="session.online"
                  size="small"
                  type="info"
                  round
                  :bordered="false"
                >
                  {{ t('sessions.online') }}
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
        <div v-show="!sessions.length && !loading" class="table-fill-empty">
          <n-empty :description="t('sessions.empty')" />
        </div>
      </n-spin>
      <p v-if="sessions.length" class="sessions-footnote">
        {{ t('sessions.footnote', { online: onlineCount, total: sessions.length }) }}
      </p>
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
.sessions-head__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.session-row {
  display: grid;
  grid-template-columns: minmax(200px, 1.2fr) minmax(0, 2fr) auto;
  align-items: center;
  gap: 16px;
  width: 100%;
}
/* 陈旧（离线）会话整体降饱和，视觉让位于活跃会话 */
.session-row--stale {
  opacity: 0.62;
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
  background: color-mix(in srgb, var(--app-primary) 9%, transparent);
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
.sessions-footnote {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--app-text-secondary);
}
@media (max-width: 860px) {
  .session-row {
    grid-template-columns: 1fr;
  }
}
</style>
