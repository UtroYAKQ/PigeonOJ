<script setup lang="ts">
/**
 * 团队邀请落地页（/teams/invites/:token，public）：
 * 解析邀请链接展示团队信息；登录用户可直接提交加入申请，
 * 未登录跳转登录页（登录后回跳）。
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { resolveTeamInvite, submitTeamApplication } from '@/api/teams'
import { message } from '@/utils/feedback'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'
import type { TeamInviteResolved } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const token = String(route.params.token)
const invite = ref<TeamInviteResolved | null>(null)
const loading = ref(false)
const submitting = ref(false)
const submitted = ref(false)

async function load() {
  loading.value = true
  try {
    invite.value = await resolveTeamInvite(token)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('teams.invite.invalid'))
  } finally {
    loading.value = false
  }
}

async function goLogin() {
  await router.push({ path: '/login', query: { redirect: route.fullPath } })
}

async function apply() {
  submitting.value = true
  try {
    await submitTeamApplication(String(invite.value?.team_id), token)
    submitted.value = true
    message.success(t('teams.invite.submitted'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}

function goTeams() {
  router.push('/teams')
}

onMounted(load)
</script>

<template>
  <div class="invite-page">
    <n-card :bordered="false" class="invite-card">
      <n-spin :show="loading">
        <template v-if="invite">
          <div class="invite-hero">
            <div class="invite-badge">{{ t('teams.invite.badge') }}</div>
            <h2 class="invite-title">{{ invite.team_name }}</h2>
            <p class="invite-meta">
              {{ t('teams.invite.expires', { time: formatDateTime(invite.expires_at) }) }}
            </p>
          </div>

          <template v-if="userStore.isLoggedIn">
            <n-alert v-if="submitted" type="success" :bordered="false" class="invite-alert">
              {{ t('teams.invite.submittedHint') }}
            </n-alert>
            <div class="invite-actions">
              <n-button v-if="!submitted" type="primary" :loading="submitting" @click="apply">
                {{ t('teams.invite.apply') }}
              </n-button>
              <n-button secondary @click="goTeams">{{ t('teams.invite.goTeams') }}</n-button>
            </div>
          </template>
          <template v-else>
            <n-alert type="info" :bordered="false" class="invite-alert">
              {{ t('teams.invite.loginRequired') }}
            </n-alert>
            <div class="invite-actions">
              <n-button type="primary" @click="goLogin">{{ t('teams.invite.goLogin') }}</n-button>
            </div>
          </template>
        </template>
        <n-empty v-else-if="!loading" :description="t('teams.invite.invalid')" size="large" />
      </n-spin>
    </n-card>
  </div>
</template>

<style scoped>
.invite-page {
  max-width: 520px;
  margin: 0 auto;
}
.invite-hero {
  text-align: center;
  padding: 24px 0 8px;
}
.invite-badge {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 999px;
  background: var(--app-muted-bg);
  color: var(--app-text-secondary);
  font-size: 12px;
}
.invite-title {
  margin: 14px 0 6px;
  font-size: 22px;
}
.invite-meta {
  color: var(--app-text-secondary);
  font-size: 13px;
}
.invite-alert {
  margin-top: 16px;
}
.invite-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
}
</style>
