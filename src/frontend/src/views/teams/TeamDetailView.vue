<script setup lang="ts">
/**
 * 团队详情主页（/teams/:id）：社区空间式布局。
 * Hero（渐变横幅 + 头像 + 简介 + 动作区）+ 模块化内容区（tab 切换 + 数据装配）：
 * 成员 / 团队题库 / 团队题单 / 团队比赛 / 加入申请（管理员），
 * 各模块面板见 ./components/*Panel.vue（面板自持列表数据与加载）。
 * 权限按 my_role 显隐（creator ⊇ admin ⊇ member）；编辑 / 邀请 / 退出解散等
 * 团队级动作收敛在本组件。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { MoreFilled, Promotion, Setting } from '@element-plus/icons-vue'
import {
  NButton,
  NDropdown,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItem,
  NIcon,
  NInput,
  NModal,
  NQrCode,
  NSkeleton,
  NSpin,
} from 'naive-ui'

import {
  createTeamInvite,
  disbandTeam,
  exitTeam,
  getTeam,
  submitTeamApplication,
  updateTeam,
} from '@/api/teams'
import { uploadImage } from '@/api/files'
import { ApiError } from '@/api/http'
import BaseAvatar from '@/components/BaseAvatar.vue'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import { useTeamsStore } from '@/stores/teams'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import TeamMembersPanel from './components/TeamMembersPanel.vue'
import TeamProblemsPanel from './components/TeamProblemsPanel.vue'
import TeamSetsPanel from './components/TeamSetsPanel.vue'
import TeamContestsPanel from './components/TeamContestsPanel.vue'
import TeamApplicationsPanel from './components/TeamApplicationsPanel.vue'
import type { TeamDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const teamId = String(route.params.id)
const team = ref<TeamDetail | null>(null)
const loadFailed = ref(false)
/** 403（非团队成员）标志：失败态下切换为「申请加入」引导而非裸错误 */
const forbidden = ref(false)
const loading = ref(false)

const isCreator = computed(() => team.value?.my_role === 'creator')
const isAdmin = computed(() => team.value?.my_role === 'creator' || team.value?.my_role === 'admin')

// ---------------- 模块 tab（内容板块） ----------------

type TeamModule = 'members' | 'problems' | 'sets' | 'contests' | 'applications'
const activeModule = ref<TeamModule>('members')

const moduleMeta = computed(() => {
  const items: Array<{
    key: TeamModule
    labelKey: string
    adminOnly?: boolean
  }> = [
    { key: 'members', labelKey: 'teams.detail.tabMembers' },
    { key: 'problems', labelKey: 'teams.modules.problems' },
    { key: 'sets', labelKey: 'teams.modules.sets' },
    { key: 'contests', labelKey: 'teams.modules.contests' },
    {
      key: 'applications',
      labelKey: 'teams.detail.tabApplications',
      adminOnly: true,
    },
  ]
  return items.filter((item) => !item.adminOnly || isAdmin.value)
})

// ---------------- 团队信息 ----------------

async function load() {
  loading.value = true
  try {
    team.value = await getTeam(teamId)
    loadFailed.value = false
    forbidden.value = false
  } catch (error) {
    loadFailed.value = true
    // 2003 = 非团队成员（详情仅成员可见）：给出申请加入出口而非裸错误
    forbidden.value = error instanceof ApiError && error.code === 2003
    message.error(error instanceof Error ? error.message : t('teams.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}

/** 非成员兜底：提交加入申请（公开团队可直接申请，私有团队 403 提示走邀请链接） */
const applying = ref(false)
function applyFromForbidden() {
  applying.value = true
  submitTeamApplication(teamId)
    .then(() => message.success(t('teams.list.applySuccess')))
    .catch((error) => {
      message.error(error instanceof Error ? error.message : t('common.operationFailed'))
    })
    .finally(() => {
      applying.value = false
    })
}

// ---------------- 面板联动 ----------------

const membersPanel = ref<InstanceType<typeof TeamMembersPanel> | null>(null)
/** tab pane 经 v-for 渲染，模板 ref 会被收集为数组，改用函数 ref 拿到唯一实例 */
function setMembersPanel(el: unknown) {
  membersPanel.value = (el as InstanceType<typeof TeamMembersPanel> | null) ?? null
}

/** 申请审批 / 移出成员后：重拉成员列表与团队概要 */
function onMembershipChanged() {
  membersPanel.value?.reload()
  void load()
}

// ---------------- 邀请（弹窗：链接 + 二维码） ----------------

const invite = reactive({ token: '', expiresAt: '' as string, show: false })
const inviting = ref(false)

async function onCreateInvite() {
  inviting.value = true
  try {
    const result = await createTeamInvite(teamId)
    invite.token = result.token
    invite.expiresAt = formatDateTime(result.expires_at)
    invite.show = true
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    inviting.value = false
  }
}

const inviteLink = computed(() =>
  invite.token ? `${window.location.origin}/teams/invites/${invite.token}` : '',
)

/** 复制团队 ID（统计行）：显示前 8 位，复制完整 ID */
async function copyTeamId() {
  try {
    await navigator.clipboard.writeText(teamId)
    message.success(t('problems.detail.copied'))
  } catch {
    message.error(t('common.operationFailed'))
  }
}

async function copyInviteLink() {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
    message.success(t('problems.detail.copied'))
  } catch {
    message.error(t('common.operationFailed'))
  }
}

// ---------------- 编辑抽屉 ----------------

const showSettings = ref(false)
const form = reactive({
  name: '',
  description: '',
  avatar_url: '' as string | null,
  visibility: 'private' as 'public' | 'private',
})
const saving = ref(false)
const uploadingAvatar = ref(false)

function openSettings() {
  if (!team.value) return
  form.name = team.value.name
  form.description = team.value.description ?? ''
  form.avatar_url = team.value.avatar_url ?? ''
  form.visibility = team.value.visibility ?? 'private'
  showSettings.value = true
}

async function onAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingAvatar.value = true
  try {
    const result = await uploadImage(file)
    form.avatar_url = result.url
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploadingAvatar.value = false
    input.value = ''
  }
}

async function saveSettings() {
  if (!form.name.trim()) {
    message.warning(t('teams.create.nameRequired'))
    return
  }
  saving.value = true
  try {
    team.value = await updateTeam(teamId, {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      avatar_url: form.avatar_url || undefined,
      visibility: form.visibility,
    })
    message.success(t('teams.settings.saved'))
    showSettings.value = false
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

// ---------------- 退出 / 解散（更多下拉） ----------------

type HeroAction = 'exit' | 'disband'

const heroActions = computed(() => {
  const actions: Array<{ key: HeroAction; label: string }> = []
  if (!isCreator.value) actions.push({ key: 'exit', label: t('teams.detail.exit') })
  if (isCreator.value) actions.push({ key: 'disband', label: t('teams.detail.disband') })
  return actions
})

function onHeroAction(key: HeroAction) {
  if (key === 'exit') onExit()
  else onDisband()
}

function onExit() {
  confirmAsyncDialog({
    title: t('teams.detail.exit'),
    content: t('teams.detail.exitConfirm'),
    positiveText: t('teams.detail.exit'),
    action: async () => {
      await exitTeam(teamId)
    },
    successMessage: t('teams.detail.exitSuccess'),
    onAfterSuccess: () => {
      // 成员关系已变更：列表页经脏标记重拉，路由回退前台团队页
      useTeamsStore().markMembershipChanged()
      void router.push('/teams/mine')
    },
  })
}

function onDisband() {
  confirmAsyncDialog({
    title: t('teams.detail.disband'),
    content: t('teams.detail.disbandConfirm'),
    positiveText: t('teams.detail.disband'),
    action: async () => {
      await disbandTeam(teamId)
    },
    successMessage: t('teams.detail.disbandSuccess'),
    onAfterSuccess: () => {
      useTeamsStore().markMembershipChanged()
      void router.push('/teams/mine')
    },
  })
}

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <div class="team-fill">
      <!-- NSpin 只包 Hero（骨架 / 失败 / 信息），不参与模块卡的高度传导 -->
      <NSpin :show="loading" class="hero-spin">
        <!-- 加载骨架 -->
        <div v-if="!team && loading" class="hero hero--skeleton">
          <NSkeleton height="140px" :sharp="false" style="border-radius: 8px" />
          <NSkeleton
            circle
            width="88px"
            height="88px"
            class="hero__avatar hero__avatar--skeleton"
          />
          <NSkeleton text style="width: 30%" />
          <NSkeleton text style="width: 60%" />
        </div>

        <!-- 加载失败（403 = 非成员：提供申请加入出口） -->
        <div v-else-if="!team && loadFailed" class="hero hero--failed">
          <NEmpty
            :description="forbidden ? t('teams.detail.forbidden') : t('teams.detail.loadFailed')"
            size="large"
          >
            <template #extra>
              <div class="hero__failed-actions">
                <NButton
                  v-if="forbidden"
                  type="primary"
                  secondary
                  :loading="applying"
                  @click="applyFromForbidden"
                >
                  {{ t('teams.list.applyJoin') }}
                </NButton>
                <NButton @click="load">{{ t('action.refresh') }}</NButton>
              </div>
            </template>
          </NEmpty>
        </div>
      </NSpin>

      <!-- ======== Hero（不参与模块卡高度链） ======== -->
      <section v-if="team" class="hero">
        <div class="hero__banner" aria-hidden="true">
          <span class="hero__orb"></span>
          <span class="hero__ring"></span>
        </div>
        <div class="hero__body">
          <BaseAvatar
            class="hero__avatar"
            kind="team"
            :src="team.avatar_url"
            :name="team.name"
            :size="88"
            :round="false"
            :radius="10"
          />

          <div class="hero__main">
            <div class="hero__title-row">
              <h1 class="hero__title">{{ team.name }}</h1>
            </div>
            <p class="hero__desc" :class="{ 'hero__desc--empty': !team.description }">
              {{ team.description ?? t('teams.detail.descEmpty') }}
            </p>
            <!-- 统计行：成员数 / 创建时间 / 团队 ID（点击复制完整 ID） -->
            <div class="hero__meta">
              <span>
                {{ t('teams.list.memberCount') }}
                <strong class="hero__meta-num">{{ team.member_count }}</strong>
              </span>
              <span class="hero__dot" aria-hidden="true">·</span>
              <span>{{ t('teams.list.createdAt') }} {{ formatDateTime(team.created_at) }}</span>
              <span class="hero__dot" aria-hidden="true">·</span>
              <button
                type="button"
                class="hero__id"
                :title="t('teams.detail.teamId')"
                @click="copyTeamId"
              >
                {{ t('teams.detail.teamId') }} {{ teamId.slice(0, 8) }}
              </button>
            </div>
          </div>

          <!-- 动作区：预留扩展位，后续团队管理按钮继续向此追加 -->
          <div class="hero__actions">
            <NButton
              v-if="isAdmin"
              type="primary"
              size="large"
              :loading="inviting"
              @click="onCreateInvite"
            >
              <template #icon>
                <NIcon :component="Promotion" />
              </template>
              {{ t('teams.detail.inviteMembers') }}
            </NButton>
            <NButton v-if="isAdmin" secondary size="large" @click="openSettings">
              <template #icon>
                <NIcon :component="Setting" />
              </template>
              {{ t('teams.detail.editInfo') }}
            </NButton>
            <NDropdown
              v-if="heroActions.length"
              trigger="click"
              :options="heroActions"
              @select="onHeroAction"
            >
              <NButton circle quaternary size="large" :aria-label="t('teams.detail.more')">
                <template #icon>
                  <NIcon :component="MoreFilled" />
                </template>
              </NButton>
            </NDropdown>
          </div>
        </div>
      </section>

      <!-- ======== 内容模块（tab 线条直连内容） ======== -->
      <section v-if="team" class="module-area">
        <n-tabs v-model:value="activeModule" type="line" class="module-tabs">
          <n-tab-pane
            v-for="moduleItem in moduleMeta"
            :key="moduleItem.key"
            :name="moduleItem.key"
            :tab="t(moduleItem.labelKey)"
            display-directive="show"
          >
            <!-- 成员 -->
            <TeamMembersPanel
              v-if="moduleItem.key === 'members'"
              :ref="setMembersPanel"
              :team-id="teamId"
              :is-creator="isCreator"
              :is-admin="isAdmin"
              @changed="load"
            />

            <!-- 团队题库 -->
            <TeamProblemsPanel
              v-else-if="moduleItem.key === 'problems'"
              :team-id="teamId"
              :is-admin="isAdmin"
            />

            <!-- 团队题单 -->
            <TeamSetsPanel
              v-else-if="moduleItem.key === 'sets'"
              :team-id="teamId"
              :is-admin="isAdmin"
            />

            <!-- 团队比赛 -->
            <TeamContestsPanel
              v-else-if="moduleItem.key === 'contests'"
              :team-id="teamId"
              :is-admin="isAdmin"
            />

            <!-- 加入申请（管理员） -->
            <TeamApplicationsPanel
              v-else
              :team-id="teamId"
              :is-admin="isAdmin"
              @changed="onMembershipChanged"
            />
          </n-tab-pane>
        </n-tabs>
      </section>
    </div>

    <!-- 邀请弹窗：二维码 + 链接 -->
    <NModal
      v-model:show="invite.show"
      preset="card"
      style="width: 440px"
      :title="t('teams.settings.inviteTitle')"
    >
      <div class="invite-modal">
        <div class="invite-modal__qr">
          <!-- padding=0：组件默认 12px 内边距在 border-box 下会挤压画布，
               右下约 24px 被容器 overflow:hidden 裁掉；留白改由外层承担 -->
          <NQrCode
            v-if="inviteLink"
            :value="inviteLink"
            :size="176"
            :padding="0"
            error-correction-level="M"
          />
        </div>
        <p class="invite-modal__hint">{{ t('teams.settings.inviteHint') }}</p>
        <div class="invite-modal__link">
          <span class="invite-modal__url" :title="inviteLink">{{ inviteLink }}</span>
          <div class="invite-modal__actions">
            <NButton size="small" type="primary" secondary @click="copyInviteLink">
              {{ t('action.copyLink') }}
            </NButton>
            <NButton size="small" quaternary :loading="inviting" @click="onCreateInvite">
              {{ t('teams.settings.regenerate') }}
            </NButton>
          </div>
        </div>
        <p class="field-hint">
          {{ t('teams.settings.inviteExpiry', { time: invite.expiresAt }) }}
        </p>
      </div>
    </NModal>

    <!-- 编辑信息抽屉 -->
    <NDrawer v-model:show="showSettings" :width="440" placement="right">
      <NDrawerContent :title="t('teams.settings.infoTitle')" closable>
        <NForm label-placement="top">
          <NFormItem :label="t('teams.create.name')" required>
            <NInput v-model:value="form.name" maxlength="64" />
          </NFormItem>
          <NFormItem :label="t('teams.create.description')">
            <NInput v-model:value="form.description" type="textarea" :rows="4" maxlength="2000" />
          </NFormItem>
          <NFormItem :label="t('teams.settings.visibility')">
            <n-radio-group v-model:value="form.visibility">
              <n-radio value="private">{{ t('teams.settings.visibilityPrivate') }}</n-radio>
              <n-radio value="public">{{ t('teams.settings.visibilityPublic') }}</n-radio>
            </n-radio-group>
            <span class="field-hint">{{ t('teams.settings.visibilityHint') }}</span>
          </NFormItem>
          <NFormItem :label="t('teams.settings.avatar')">
            <div class="avatar-uploader">
              <div class="avatar-preview" :class="{ empty: !form.avatar_url }">
                <img v-if="form.avatar_url" :src="form.avatar_url" alt="" />
                <span v-else>{{ t('teams.settings.noAvatar') }}</span>
              </div>
              <label class="avatar-upload-btn">
                <input type="file" accept="image/*" hidden @change="onAvatarChange" />
                <NButton size="small" :loading="uploadingAvatar" tag="span">
                  {{ t('teams.settings.avatar') }}
                </NButton>
              </label>
              <span class="field-hint">{{ t('contests.list.logoHint') }}</span>
            </div>
          </NFormItem>
        </NForm>
        <template #footer>
          <div class="drawer-footer">
            <NButton @click="showSettings = false">{{ t('action.cancel') }}</NButton>
            <NButton type="primary" :loading="saving" @click="saveSettings">
              {{ t('action.save') }}
            </NButton>
          </div>
        </template>
      </NDrawerContent>
    </NDrawer>
  </WorkbenchShell>
</template>

<style scoped>
/* ============================================================
   通铺沉浸式布局：page-fill → n-card-content（零 padding）
   → team-fill（无外框、无卡片嵌套，线条分隔）
   ============================================================ */
.team-fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  /* 抵消应用壳卡片默认 padding：内容直接铺满，顶部无间距 */
  margin: calc(-1 * var(--n-padding-top, 20px)) calc(-1 * var(--n-padding-left, 24px))
    calc(-1 * var(--n-padding-bottom, 24px));
}

/* ======== Hero：中性底 + 主色几何 ========
   规则同 ContestDetailView 的 Hero：主色仅小面积点缀，不大面积铺色。
   底色比卡片深一档（surface-muted），主色只以「被裁切的圆」出现：
   右上实心巨弧 + 右下描边环，画面内不留完整圆形。 */
.hero {
  position: relative;
  flex-shrink: 0;
  border-bottom: 1px solid var(--app-border);
  background:
    radial-gradient(
      90% 220% at 97% 112%,
      color-mix(in srgb, var(--app-primary) 6%, transparent) 0%,
      transparent 62%
    ),
    radial-gradient(
      120% 180% at 0% 0%,
      color-mix(in srgb, var(--app-primary) 5%, transparent) 0%,
      transparent 52%
    ),
    var(--app-surface-muted, #f7f7fa);
  overflow: hidden;
}
.hero--skeleton {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-start;
}
.hero--failed {
  padding: 48px 24px;
  display: flex;
  justify-content: center;
}
.hero__failed-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}
.hero__avatar--skeleton {
  margin: -44px 0 0 28px;
}
/* 巨圆：圆心落在上沿外 252px，只露出底部一弧；
   填充用径向渐变（20% → 5% → 0），边缘化开，避免出现生硬的色块边界 */
.hero__orb {
  position: absolute;
  width: 340px;
  height: 340px;
  border-radius: 999px;
  right: 7%;
  top: -252px;
  background: radial-gradient(
    circle at 50% 50%,
    color-mix(in srgb, var(--app-primary) 20%, transparent) 0%,
    color-mix(in srgb, var(--app-primary) 5%, transparent) 58%,
    transparent 74%
  );
}
/* 描边环：被右侧与底部各裁一截，与上方实心弧形成一虚一实 */
.hero__ring {
  position: absolute;
  width: 228px;
  height: 228px;
  border-radius: 999px;
  right: -104px;
  bottom: -120px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 24%, transparent);
}
.hero__body {
  position: relative;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 26px 32px 20px;
  flex-wrap: wrap;
  max-width: 1680px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}
/* 头像框架由 BaseAvatar（尺寸 / 圆角 / 回退图）承担，这里只保留 Hero 描边与投影 */
.hero__avatar {
  border: 3px solid var(--app-card-bg, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 8%);
}
.hero__main {
  flex: 1;
  min-width: 240px;
  display: grid;
  gap: 4px;
}
.hero__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.hero__title {
  margin: 0;
  line-height: 1.2;
  font-size: 22px;
  font-weight: 700;
  color: var(--app-text);
}
.hero__desc {
  margin: 0;
  color: var(--app-text);
  font-size: 13px;
  line-height: 1.6;
  max-width: 720px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hero__desc--empty {
  color: var(--app-text-secondary);
  opacity: 0.6;
}
.hero__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--app-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.hero__dot {
  opacity: 0.5;
}
.hero__meta-num {
  font-weight: 600;
  color: var(--app-text);
}
/* 团队 ID：点击复制完整 ID，常态是弱化的文字而不是按钮 */
.hero__id {
  padding: 0;
  border: none;
  background: none;
  font: inherit;
  color: inherit;
  cursor: pointer;
  font-variant-numeric: tabular-nums;
  border-bottom: 1px dashed var(--app-border-strong);
  transition: color 0.15s ease;
}
.hero__id:hover {
  color: var(--app-primary);
}
/* 动作区：预留扩展位，后续按钮直接追加；窄屏自动换行 */
.hero__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-left: auto;
}

/* ======== 模块区：tab 线条直连内容，无卡片外框 ======== */
.module-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tabs-nav) {
  padding: 4px 32px 0;
  flex-shrink: 0;
}
.module-tabs :deep(.n-tabs-tab) {
  font-size: 14px;
  padding: 12px 6px;
}
/* 非 animated 模式 naive 不渲染 pane-wrapper，pane 直接挂在 .n-tabs 下 */
.module-tabs :deep(.n-tabs-pane-wrapper),
.module-tabs :deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tab-pane) {
  padding: 16px 32px 20px;
}

/* ======== 邀请弹窗 ======== */
.invite-modal {
  display: grid;
  justify-items: center;
  gap: 12px;
}
.invite-modal__qr {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  overflow: hidden;
  /* 组件 padding=0，留白由外层承担，同时避免圆角裁到码点 */
  padding: 10px;
}
.invite-modal__hint {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  text-align: center;
}
.invite-modal__link {
  width: 100%;
  display: grid;
  gap: 8px;
}
.invite-modal__url {
  font-size: 12px;
  color: var(--app-text-secondary);
  word-break: break-all;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.invite-modal__actions {
  display: flex;
  justify-content: center;
  gap: 8px;
}
.field-hint {
  color: var(--app-text-secondary);
  font-size: 12px;
  margin: 0;
}

/* ======== 编辑抽屉 ======== */
.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.avatar-uploader {
  display: flex;
  align-items: center;
  gap: 12px;
}
.avatar-preview {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  border: 1px solid var(--app-border);
  display: grid;
  place-items: center;
  overflow: hidden;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-upload-btn {
  cursor: pointer;
}

/* 响应式 */
@media (max-width: 860px) {
  .hero__actions {
    margin-left: 0;
    width: 100%;
  }
  .hero__body {
    padding: 20px 16px;
  }
  .hero__avatar {
    width: 72px;
    height: 72px;
  }
  .module-tabs :deep(.n-tabs-nav),
  .module-tabs :deep(.n-tab-pane) {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
