<script setup lang="ts">
/**
 * 团队邀请落地页（/teams/invites/:token，public）：
 * 解析邀请链接展示团队信息；登录用户可直接提交加入申请，
 * 未登录跳转登录页（登录后回跳）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { AlarmClock, Loader2, LogIn, RefreshCw, Users } from '@lucide/vue'

import { resolveTeamInvite, submitTeamApplication } from '@/api/teams'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { TeamInviteResolved } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const token = computed(() => String(route.params.token))
const invite = ref<TeamInviteResolved | null>(null)
const loading = ref(true)
const submitting = ref(false)
const submitted = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    invite.value = await resolveTeamInvite(token.value)
  } catch (error) {
    invite.value = null
    message.error(error instanceof Error ? error.message : t('teams.invite.invalid'))
  } finally {
    loading.value = false
  }
}

function goLogin(): void {
  void router.push({ path: '/login', query: { redirect: route.fullPath } })
}

function goTeams(): void {
  void router.push('/teams/mine')
}

async function apply(): Promise<void> {
  if (!invite.value || submitting.value) return
  submitting.value = true
  try {
    await submitTeamApplication(invite.value.team_id, token.value)
    submitted.value = true
    message.success(t('teams.invite.submitted'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('teams.invite.title')">
    <div class="grid min-h-0 flex-1 place-items-center">
      <div v-if="loading" class="flex items-center gap-2 text-[13px] text-muted-foreground">
        <Loader2 class="size-5 animate-spin" />
        {{ t('common.loading') }}
      </div>

      <div
        v-else-if="!invite"
        class="flex w-full max-w-[520px] flex-col items-center gap-3 rounded-xl border border-border bg-card px-6 py-12 text-center"
      >
        <EmptyState :icon="Users" :text="t('teams.invite.invalid')">
          <Button variant="outline" size="sm" @click="load">
            <RefreshCw class="size-3.5" />
            {{ t('action.refresh') }}
          </Button>
        </EmptyState>
      </div>

      <article
        v-else
        class="w-full max-w-[520px] rounded-xl border border-border bg-card px-6 py-8 text-center sm:px-8"
      >
        <Badge variant="outline" class="h-6 border px-2.5 text-[11.5px] font-medium">
          {{ t('teams.invite.badge') }}
        </Badge>

        <BaseAvatar
          kind="team"
          :src="invite.avatar_url"
          :name="invite.team_name"
          :size="72"
          :round="false"
          :radius="16"
          bordered
          class="mt-5"
        />

        <p class="mt-4 text-[13px] text-muted-foreground">{{ t('teams.invite.subtitle') }}</p>
        <h1 class="mt-1 break-words text-[24px] font-semibold leading-tight tracking-tight">
          {{ invite.team_name }}
        </h1>

        <p
          class="mt-4 inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2.5 py-1 text-[12px] tabular-nums text-muted-foreground"
        >
          <AlarmClock class="size-3.5" />
          {{ t('teams.invite.expires', { time: formatDateTime(invite.expires_at) }) }}
        </p>

        <template v-if="userStore.isLoggedIn">
          <InlineNotice v-if="submitted" tone="success" class="mt-6">
            {{ t('teams.invite.submittedHint') }}
          </InlineNotice>
          <div class="mt-6 flex flex-wrap items-center justify-center gap-2">
            <Button v-if="!submitted" size="lg" :disabled="submitting" @click="apply">
              <Loader2 v-if="submitting" class="size-4 animate-spin" />
              {{ t('teams.invite.apply') }}
            </Button>
            <Button variant="outline" size="lg" @click="goTeams">
              {{ t('teams.invite.goTeams') }}
            </Button>
          </div>
        </template>

        <template v-else>
          <InlineNotice tone="info" class="mt-6">
            {{ t('teams.invite.loginRequired') }}
          </InlineNotice>
          <div class="mt-4 flex justify-center">
            <Button size="lg" @click="goLogin">
              <LogIn class="size-4" />
              {{ t('teams.invite.goLogin') }}
            </Button>
          </div>
        </template>
      </article>
    </div>
  </WorkbenchShell>
</template>
