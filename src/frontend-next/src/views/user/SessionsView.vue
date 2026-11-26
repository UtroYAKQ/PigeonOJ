<script setup lang="ts">
/**
 * 会话管理（/user/sessions）：活跃设备列表 + 在线态 + 精准下线。
 * 在线判定随服务端（5 分钟内有活动）；同设备重复登录由后端去重（登录替换旧会话）。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Monitor, Smartphone, Tablet } from '@lucide/vue'

import * as usersApi from '@/api/users'
import LineList from '@/components/common/LineList.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { Button } from '@/components/ui/button'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { UserSession } from '@/types'
import UserSettingsShell from './components/UserSettingsShell.vue'

const { t } = useI18n()

const sessions = ref<UserSession[]>([])
const loading = ref(false)
const revokingOthers = ref(false)

const othersCount = computed(() => sessions.value.filter((item) => !item.current).length)
const onlineCount = computed(() => sessions.value.filter((item) => item.online).length)

async function load(): Promise<void> {
  loading.value = true
  try {
    sessions.value = await usersApi.listSessions()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function onRevoke(session: UserSession): Promise<void> {
  const ok = await confirmDialog({
    title: t('sessions.revokeTitle'),
    content: t('sessions.revokeConfirm', {
      device: session.device_info ?? t('common.unknownDevice'),
    }),
    positiveText: t('action.revoke'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await usersApi.revokeSession(session.id)
    message.success(t('sessions.revoked'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

async function onRevokeOthers(): Promise<void> {
  const ok = await confirmDialog({
    title: t('sessions.revokeOthersTitle'),
    content: t('sessions.revokeOthersConfirm', { count: othersCount.value }),
    positiveText: t('sessions.revokeOthers'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  revokingOthers.value = true
  try {
    await usersApi.revokeOtherSessions()
    message.success(t('sessions.revokedOthers', { count: othersCount.value }))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    revokingOthers.value = false
  }
}

/** 设备形态图标：mobile / tablet / desktop（依据 device_info + UA 关键词，缺省显示器） */
function deviceIcon(session: UserSession) {
  const info = `${session.device_info ?? ''} ${session.user_agent ?? ''}`
  if (/移动端|mobile|iPhone|Android/i.test(info)) return Smartphone
  if (/平板|tablet|iPad/i.test(info)) return Tablet
  return Monitor
}
</script>

<template>
  <UserSettingsShell>
    <section class="flex min-h-0 flex-1 flex-col">
      <header
        class="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3.5"
      >
        <h2 class="text-[14px] font-semibold">{{ t('sessions.title') }}</h2>
        <div class="flex items-center gap-2">
          <Button
            v-if="othersCount > 0"
            variant="outline"
            size="sm"
            class="h-8"
            :disabled="revokingOthers"
            @click="onRevokeOthers"
          >
            <Loader2 v-if="revokingOthers" class="size-3.5 animate-spin" />
            {{ t('sessions.revokeOthers') }}（{{ othersCount }}）
          </Button>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </div>
      </header>

      <LineList
        :items="sessions"
        :loading="loading && !sessions.length"
        :empty-text="t('sessions.empty')"
        :get-key="(session: UserSession) => session.id"
      >
        <template #skeleton>
          <div v-for="index in 3" :key="index" class="flex items-center gap-3 px-5 py-4">
            <div class="size-9 shrink-0 animate-pulse rounded-md bg-muted" />
            <div class="space-y-1.5">
              <div class="h-3 w-40 animate-pulse rounded bg-muted" />
              <div class="h-2.5 w-64 animate-pulse rounded bg-muted" />
            </div>
          </div>
        </template>

        <template #item="{ item: session }">
          <div
            class="flex flex-wrap items-center gap-3 px-5 py-3.5 transition-opacity"
            :class="session.online ? '' : 'opacity-65'"
          >
            <span
              class="grid size-9 shrink-0 place-items-center rounded-md border border-border bg-surface text-muted-foreground"
            >
              <component :is="deviceIcon(session)" class="size-4" :stroke-width="1.8" />
            </span>

            <div class="min-w-0 flex-1 basis-[220px]">
              <div class="flex flex-wrap items-center gap-2">
                <strong class="truncate text-[13px] font-medium">
                  {{ session.device_info ?? t('common.unknownDevice') }}
                </strong>
                <ToneBadge v-if="session.current" tone="success" :label="t('common.current')" />
                <ToneBadge v-else-if="session.online" tone="info" :label="t('sessions.online')" />
              </div>
              <p class="mt-0.5 text-[11.5px] text-muted-foreground">
                {{ session.ip_address ?? '--' }}
                <template v-if="session.location"> · {{ session.location }}</template>
              </p>
            </div>

            <dl class="flex min-w-0 flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-muted-foreground">
              <div class="flex gap-1">
                <dt>{{ t('sessions.lastActive') }}:</dt>
                <dd class="tabular-nums">{{ formatDateTime(session.last_active_at) }}</dd>
              </div>
              <div class="flex gap-1">
                <dt>{{ t('sessions.loginAt') }}:</dt>
                <dd class="tabular-nums">{{ formatDateTime(session.created_at) }}</dd>
              </div>
              <div class="flex gap-1">
                <dt>{{ t('sessions.expiresAt') }}:</dt>
                <dd class="tabular-nums">{{ formatDateTime(session.expires_at) }}</dd>
              </div>
            </dl>

            <div class="ml-auto shrink-0">
              <span v-if="session.current" class="text-[12px] text-muted-foreground">
                {{ t('sessions.currentSession') }}
              </span>
              <Button
                v-else
                variant="ghost"
                size="sm"
                class="h-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                @click="onRevoke(session)"
              >
                {{ t('action.revoke') }}
              </Button>
            </div>
          </div>
        </template>
      </LineList>

      <p
        v-if="sessions.length"
        class="border-t border-border px-5 py-2.5 text-[11.5px] text-muted-foreground"
      >
        {{ t('sessions.footnote', { online: onlineCount, total: sessions.length }) }}
      </p>
    </section>
  </UserSettingsShell>
</template>
