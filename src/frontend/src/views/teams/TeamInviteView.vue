<script setup lang="ts">
/**
 * 团队邀请落地页（/teams/invites/:token，public）：
 * 解析邀请链接展示团队信息；登录用户可直接提交加入申请，
 * 未登录跳转登录页（登录后回跳）。
 * 布局复用 WorkbenchShell（page-fill 占满应用壳），内部居中舞台 +
 * 主色几何装饰，风格对齐 TeamDetailView 的 Hero（主色仅小面积点缀）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { AlarmClock } from '@element-plus/icons-vue'

import { resolveTeamInvite, submitTeamApplication } from '@/api/teams'
import { message } from '@/utils/feedback'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
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

const initial = computed(
  () => (invite.value?.team_name ?? '').trim().charAt(0).toUpperCase() || 'T',
)

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
  <WorkbenchShell>
    <div class="invite-page">
      <!-- 装饰层：被视口裁切的主色几何，一实一虚 -->
      <div class="invite-art" aria-hidden="true">
        <span class="invite-art__orb"></span>
        <span class="invite-art__ring"></span>
      </div>

      <!-- spin 只包主内容；空态为兄弟节点以 table-fill-empty 居中（frontend.md 空态样板） -->
      <n-spin v-show="loading || invite" :show="loading" class="table-fill invite-spin">
        <div v-if="invite" class="invite-stage">
          <div class="invite-hero">
            <span class="invite-hero__badge">{{ t('teams.invite.badge') }}</span>
            <img
              v-if="invite.avatar_url"
              :src="invite.avatar_url"
              alt=""
              class="invite-hero__avatar"
            />
            <div v-else class="invite-hero__avatar" aria-hidden="true">{{ initial }}</div>
            <p class="invite-hero__kicker">{{ t('teams.invite.subtitle') }}</p>
            <h1 class="invite-hero__name">{{ invite.team_name }}</h1>
            <p class="invite-hero__meta">
              <n-icon :component="AlarmClock" />
              <span>{{
                t('teams.invite.expires', { time: formatDateTime(invite.expires_at) })
              }}</span>
            </p>

            <template v-if="userStore.isLoggedIn">
              <n-alert v-if="submitted" type="success" :bordered="false" class="invite-hero__alert">
                {{ t('teams.invite.submittedHint') }}
              </n-alert>
              <div class="invite-hero__actions">
                <n-button
                  v-if="!submitted"
                  type="primary"
                  size="large"
                  :loading="submitting"
                  @click="apply"
                >
                  {{ t('teams.invite.apply') }}
                </n-button>
                <n-button size="large" secondary @click="goTeams">
                  {{ t('teams.invite.goTeams') }}
                </n-button>
              </div>
            </template>
            <template v-else>
              <n-alert type="info" :bordered="false" class="invite-hero__alert">
                {{ t('teams.invite.loginRequired') }}
              </n-alert>
              <div class="invite-hero__actions">
                <n-button type="primary" size="large" @click="goLogin">
                  {{ t('teams.invite.goLogin') }}
                </n-button>
              </div>
            </template>
          </div>
        </div>
      </n-spin>

      <div v-show="!loading && !invite" class="table-fill-empty invite-empty">
        <n-empty :description="t('teams.invite.invalid')" size="large" />
      </div>
    </div>
  </WorkbenchShell>
</template>

<style scoped>
/* ============================================================
   通铺沉浸式布局（同 TeamDetailView）：page-fill → n-card-content
   → invite-page 抵消卡片 padding，装饰与内容直接铺满应用壳
   ============================================================ */
.invite-page {
  flex: 1;
  min-height: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin: calc(-1 * var(--n-padding-top, 20px)) calc(-1 * var(--n-padding-left, 24px))
    calc(-1 * var(--n-padding-bottom, 24px));
  background:
    radial-gradient(
      60% 90% at 100% 0%,
      color-mix(in srgb, var(--app-primary) 6%, transparent) 0%,
      transparent 60%
    ),
    radial-gradient(
      50% 70% at 0% 100%,
      color-mix(in srgb, var(--app-primary) 4%, transparent) 0%,
      transparent 55%
    );
}
/* 装饰层与内容分属绝对/文档流，内容侧提升保证盖在装饰之上 */
.invite-page > .table-fill,
.invite-empty {
  position: relative;
  z-index: 1;
}

/* ======== 装饰：主色仅小面积点缀，画面内不留完整圆形 ======== */
.invite-art {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.invite-art__orb {
  position: absolute;
  width: 340px;
  height: 340px;
  border-radius: 999px;
  right: -150px;
  top: -190px;
  background: radial-gradient(
    circle at 50% 62%,
    color-mix(in srgb, var(--app-primary) 16%, transparent) 0%,
    color-mix(in srgb, var(--app-primary) 5%, transparent) 56%,
    transparent 74%
  );
}
.invite-art__ring {
  position: absolute;
  width: 260px;
  height: 260px;
  border-radius: 999px;
  left: -120px;
  bottom: -130px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 22%, transparent);
}

/* ======== 居中舞台与邀请卡主体 ========
   高度链用 flex 拉伸（同 TeamDetailView.pane-spin 模式）：
   .page-fill 链上只有 min-height，height:100% 百分比解析会失败导致卡片不居中；
   spin-content 以 flex:1 吃满 spin-container，stage 再 place-items 居中 */
.invite-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
}
.invite-stage {
  flex: 1;
  min-height: 0;
  display: grid;
  place-items: center;
  padding: 48px 24px;
}
.invite-hero {
  width: 100%;
  max-width: 460px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.invite-hero__badge {
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--app-primary);
  background: color-mix(in srgb, var(--app-primary) 9%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--app-primary) 22%, transparent);
}
.invite-hero__avatar {
  width: 80px;
  height: 80px;
  margin-top: 20px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  font-size: 32px;
  font-weight: 800;
  color: var(--app-primary);
  background:
    radial-gradient(
      120% 120% at 20% 12%,
      color-mix(in srgb, var(--app-primary) 14%, transparent) 0%,
      transparent 60%
    ),
    var(--app-muted-bg);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--app-primary) 24%, transparent);
}
/* 团队头像图片：盖住占位底色，object-fit 防拉伸 */
img.invite-hero__avatar {
  object-fit: cover;
  background: var(--app-muted-bg);
}
.invite-hero__kicker {
  margin: 20px 0 0;
  color: var(--app-text-secondary);
  font-size: 14px;
}
.invite-hero__name {
  margin: 6px 0 14px;
  font-size: 26px;
  font-weight: 700;
  line-height: 1.25;
  color: var(--app-text);
  word-break: break-word;
}
.invite-hero__meta {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  background: var(--app-muted-bg);
  color: var(--app-text-secondary);
  font-size: 12.5px;
}
.invite-hero__alert {
  width: 100%;
  margin-top: 24px;
}
.invite-hero__actions {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}
/* 提示条与按钮组之间的间距收紧（与 meta → 提示条的 24px 区分层级） */
.invite-hero__alert + .invite-hero__actions {
  margin-top: 16px;
}

/* ======== 窄屏：收紧留白与字号 ======== */
@media (max-width: 640px) {
  .invite-stage {
    padding: 32px 16px;
  }
  .invite-hero__name {
    font-size: 22px;
  }
  .invite-hero__avatar {
    width: 68px;
    height: 68px;
    border-radius: 14px;
    font-size: 27px;
  }
}
</style>
