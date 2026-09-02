<script setup lang="ts">
/**
 * 团队详情主页（/teams/:id）：社区空间式布局。
 * Hero（渐变横幅 + 头像 + 简介 + 动作区）+ 模块化内容区：
 * 成员 / 团队题库 / 团队题单 / 团队比赛（预留占位）/ 加入申请（管理员）。
 * 邀请走弹窗（链接 + 二维码）；编辑走抽屉；权限按 my_role 显隐（creator ⊇ admin ⊇ member）。
 * Hero 动作区预留扩展：后续团队管理动作（如批量导入、公告等）继续向该区追加。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Collection,
  Document,
  MoreFilled,
  Promotion,
  Setting,
  Trophy,
} from '@element-plus/icons-vue'
import {
  NAvatar,
  NAvatarGroup,
  NButton,
  NDropdown,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItem,
  NGradientText,
  NIcon,
  NInput,
  NModal,
  NQrCode,
  NSkeleton,
  NSpin,
  NTag,
} from 'naive-ui'

import {
  createTeamInvite,
  disbandTeam,
  exitTeam,
  getTeam,
  kickTeamMember,
  listTeamApplications,
  listTeamMembers,
  reviewTeamApplication,
  setTeamAdmin,
  updateTeam,
} from '@/api/teams'
import { uploadImage } from '@/api/files'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { TeamApplicationItem, TeamDetail, TeamMemberItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const teamId = String(route.params.id)
const team = ref<TeamDetail | null>(null)
const loadFailed = ref(false)
const loading = ref(false)

const isCreator = computed(() => team.value?.my_role === 'creator')
const isAdmin = computed(() => team.value?.my_role === 'creator' || team.value?.my_role === 'admin')

function initialOf(name: string | null | undefined) {
  return name?.trim()?.charAt(0).toUpperCase() || 'T'
}

// ---------------- 模块 tab（内容板块；题库 / 题单 / 比赛为预留占位） ----------------

type TeamModule = 'members' | 'problems' | 'sets' | 'contests' | 'applications'
const activeModule = ref<TeamModule>('members')

const moduleMeta = computed(() => {
  const items: Array<{
    key: TeamModule
    labelKey: string
    icon: typeof Collection
    adminOnly?: boolean
    placeholder?: boolean
  }> = [
    { key: 'members', labelKey: 'teams.detail.tabMembers', icon: Setting },
    { key: 'problems', labelKey: 'teams.modules.problems', icon: Collection, placeholder: true },
    { key: 'sets', labelKey: 'teams.modules.sets', icon: Document, placeholder: true },
    { key: 'contests', labelKey: 'teams.modules.contests', icon: Trophy, placeholder: true },
    {
      key: 'applications',
      labelKey: 'teams.detail.tabApplications',
      icon: Promotion,
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
  } catch (error) {
    loadFailed.value = true
    message.error(error instanceof Error ? error.message : t('teams.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}

// ---------------- 成员 ----------------

const members = ref<TeamMemberItem[]>([])
const membersLoading = ref(false)
const {
  page: memberPage,
  pageSize: memberPageSize,
  total: memberTotal,
  changePage: changeMemberPage,
  changeSize: changeMemberSize,
} = usePagination({ defaultPageSize: 10 })

async function loadMembers() {
  membersLoading.value = true
  try {
    const result = await listTeamMembers(teamId, {
      page: memberPage.value,
      page_size: memberPageSize.value,
    })
    members.value = result.items
    memberTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    membersLoading.value = false
  }
}

/** 成员行操作（⋯ 下拉）：设 / 撤管理员（仅创建者）、移出（管理员） */
type MemberAction = 'grant' | 'revoke' | 'kick'

function memberActions(row: TeamMemberItem): Array<{ key: MemberAction; label: string }> {
  const actions: Array<{ key: MemberAction; label: string }> = []
  if (isCreator.value && !row.is_creator) {
    actions.push({
      key: row.is_admin ? 'revoke' : 'grant',
      label: t(row.is_admin ? 'teams.members.revokeAdmin' : 'teams.members.grantAdmin'),
    })
  }
  if (isAdmin.value && !row.is_creator) {
    actions.push({ key: 'kick', label: t('teams.members.kick') })
  }
  return actions
}

function onMemberAction(action: MemberAction, row: TeamMemberItem) {
  if (action === 'grant' || action === 'revoke') {
    void onSetAdmin(row, action === 'grant')
    return
  }
  onKick(row)
}

async function onSetAdmin(row: TeamMemberItem, grant: boolean) {
  try {
    await setTeamAdmin(teamId, row.user_id, grant)
    message.success(t(grant ? 'teams.members.grantSuccess' : 'teams.members.revokeSuccess'))
    await loadMembers()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function onKick(row: TeamMemberItem) {
  confirmAsyncDialog({
    title: t('teams.members.kick'),
    content: t('teams.members.kickConfirm', { name: row.nickname }),
    positiveText: t('teams.members.kick'),
    action: async () => {
      await kickTeamMember(teamId, row.user_id)
    },
    successMessage: t('teams.members.kickSuccess'),
    onAfterSuccess: () => {
      loadMembers()
      load()
    },
  })
}

// ---------------- 加入申请 ----------------

const applications = ref<TeamApplicationItem[]>([])
const applicationsLoading = ref(false)

async function loadApplications() {
  if (!isAdmin.value) return
  applicationsLoading.value = true
  try {
    const result = await listTeamApplications(teamId, { page: 1, page_size: 50 })
    applications.value = result.items
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    applicationsLoading.value = false
  }
}

async function onReview(row: TeamApplicationItem, approve: boolean) {
  try {
    await reviewTeamApplication(teamId, row.id, approve)
    message.success(
      t(approve ? 'teams.applications.approveSuccess' : 'teams.applications.rejectSuccess'),
    )
    await Promise.all([loadApplications(), loadMembers(), load()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
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
const form = reactive({ name: '', description: '', avatar_url: '' as string | null })
const saving = ref(false)
const uploadingAvatar = ref(false)

function openSettings() {
  if (!team.value) return
  form.name = team.value.name
  form.description = team.value.description ?? ''
  form.avatar_url = team.value.avatar_url ?? ''
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
      void router.push('/teams/mine')
    },
  })
}

// ---------------- 初始化 ----------------

watch(
  () => team.value?.id,
  () => {
    if (team.value) {
      loadMembers()
      loadApplications()
    }
  },
)

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
        <NSkeleton circle width="88px" height="88px" class="hero__avatar hero__avatar--skeleton" />
        <NSkeleton text style="width: 30%" />
        <NSkeleton text style="width: 60%" />
      </div>

      <!-- 加载失败 -->
      <div v-else-if="!team && loadFailed" class="hero hero--failed">
        <NEmpty :description="t('teams.detail.loadFailed')" size="large">
          <template #extra>
            <NButton @click="load">{{ t('action.refresh') }}</NButton>
          </template>
        </NEmpty>
      </div>
      </NSpin>

      <!-- ======== Hero（不参与模块卡高度链） ======== -->
      <section v-if="team" class="hero">
          <div class="hero__banner" aria-hidden="true">
            <span class="hero__orb"></span>
          </div>
          <div class="hero__body">
            <img v-if="team.avatar_url" :src="team.avatar_url" alt="" class="hero__avatar" />
            <div v-else class="hero__avatar hero__avatar--fallback" aria-hidden="true">
              {{ initialOf(team.name) }}
            </div>

            <div class="hero__main">
              <div class="hero__title-row">
                <h1 class="hero__title">
                  <NGradientText type="primary" :font-size="26">
                    {{ team.name }}
                  </NGradientText>
                </h1>
              </div>
              <p class="hero__desc" :class="{ 'hero__desc--empty': !team.description }">
                {{ team.description ?? t('teams.detail.descEmpty') }}
              </p>
              <div class="hero__meta">
                <span>{{ t('teams.list.memberCount') }} {{ team.member_count }}</span>
                <span class="hero__dot" aria-hidden="true">·</span>
                <span>{{ t('teams.list.createdAt') }} {{ formatDateTime(team.created_at) }}</span>
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
            >
              <!-- 成员 -->
              <template v-if="moduleItem.key === 'members'">
                <div class="members-head">
                  <NAvatarGroup :max="10" :size="38" class="members-head__wall">
                    <NAvatar
                      v-for="member in members.slice(0, 10)"
                      :key="member.user_id"
                      :src="member.avatar_url || undefined"
                      round
                      :style="{ color: 'var(--app-text-secondary)', fontSize: '14px' }"
                    >
                      {{ initialOf(member.nickname) }}
                    </NAvatar>
                  </NAvatarGroup>
                  <span class="members-head__count">
                    {{ t('teams.list.memberCount') }}
                    <strong>{{ team.member_count }}</strong>
                  </span>
                </div>

                <div class="pane-scroll">
                  <NSpin :show="membersLoading" class="pane-spin">
                    <ul v-if="members.length" class="member-grid">
                      <li v-for="member in members" :key="member.user_id" class="member-cell">
                        <NAvatar
                          :src="member.avatar_url || undefined"
                          round
                          :size="44"
                          :style="{
                            color: 'var(--app-text-secondary)',
                            fontSize: '15px',
                            flexShrink: 0,
                          }"
                        >
                          {{ initialOf(member.nickname) }}
                        </NAvatar>
                        <div class="member-cell__main">
                          <span class="member-cell__name" :title="member.nickname">
                            {{ member.nickname }}
                          </span>
                          <span class="member-cell__time">
                            {{ t('teams.members.joinedAt') }} {{ formatDateTime(member.joined_at) }}
                          </span>
                        </div>
                        <NTag
                          size="small"
                          round
                          :bordered="false"
                          :type="
                            member.is_creator ? 'warning' : member.is_admin ? 'info' : 'default'
                          "
                          class="member-cell__role"
                        >
                          {{
                            member.is_creator
                              ? t('teams.role.creator')
                              : member.is_admin
                                ? t('teams.role.admin')
                                : t('teams.role.member')
                          }}
                        </NTag>
                        <NDropdown
                          v-if="memberActions(member).length"
                          trigger="click"
                          :options="memberActions(member)"
                          @select="(action: MemberAction) => onMemberAction(action, member)"
                        >
                          <NButton
                            circle
                            quaternary
                            size="tiny"
                            :aria-label="t('teams.detail.more')"
                          >
                            <template #icon>
                              <NIcon :component="MoreFilled" />
                            </template>
                          </NButton>
                        </NDropdown>
                      </li>
                    </ul>
                    <NEmpty
                      v-else-if="!membersLoading"
                      :description="t('teams.members.empty')"
                      size="large"
                      class="pane-empty"
                    />
                  </NSpin>
                </div>

                <div v-if="memberTotal > memberPageSize" class="pane-pager">
                  <n-pagination
                    :page="memberPage"
                    :page-size="memberPageSize"
                    :item-count="memberTotal"
                    :page-sizes="[10, 20, 50]"
                    show-size-picker
                    @update:page="
                      (p: number) => {
                        changeMemberPage(p)
                        loadMembers()
                      }
                    "
                    @update:page-size="
                      (s: number) => {
                        changeMemberSize(s)
                        loadMembers()
                      }
                    "
                  />
                </div>
              </template>

              <!-- 预留占位：团队题库 / 题单 / 比赛 -->
              <template v-else-if="moduleItem.placeholder">
                <div class="module-placeholder">
                  <span class="module-placeholder__icon" aria-hidden="true">
                    <NIcon :size="42" :component="moduleItem.icon" />
                  </span>
                  <h3 class="module-placeholder__title">{{ t(moduleItem.labelKey) }}</h3>
                  <p class="module-placeholder__hint">{{ t('teams.modules.comingSoon') }}</p>
                </div>
              </template>

              <!-- 加入申请（管理员） -->
              <template v-else>
                <div class="pane-scroll">
                  <NSpin :show="applicationsLoading" class="pane-spin">
                    <ul v-if="applications.length" class="member-grid">
                      <li
                        v-for="application in applications"
                        :key="application.id"
                        class="member-cell"
                      >
                        <NAvatar
                          round
                          :size="44"
                          :style="{
                            color: 'var(--app-text-secondary)',
                            fontSize: '15px',
                            flexShrink: 0,
                          }"
                        >
                          {{ initialOf(application.nickname) }}
                        </NAvatar>
                        <div class="member-cell__main">
                          <span class="member-cell__name" :title="application.nickname">
                            {{ application.nickname }}
                          </span>
                          <span class="member-cell__time">
                            {{ formatDateTime(application.applied_at) }}
                          </span>
                        </div>
                        <NTag
                          size="small"
                          round
                          :bordered="false"
                          :type="application.invite_token ? 'info' : 'default'"
                          class="member-cell__role"
                        >
                          {{
                            application.invite_token
                              ? t('teams.applications.viaInvite')
                              : t('teams.applications.direct')
                          }}
                        </NTag>
                        <div class="member-cell__actions">
                          <NButton size="small" type="primary" @click="onReview(application, true)">
                            {{ t('teams.applications.approve') }}
                          </NButton>
                          <NButton
                            size="small"
                            quaternary
                            type="error"
                            @click="onReview(application, false)"
                          >
                            {{ t('teams.applications.reject') }}
                          </NButton>
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
          <NQrCode v-if="inviteLink" :value="inviteLink" :size="176" error-correction-level="M" />
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

/* ======== Hero：渐变横幅从壳顶通铺 ======== */
.hero {
  position: relative;
  flex-shrink: 0;
  border-bottom: 1px solid var(--app-border);
  background:
    linear-gradient(
      115deg,
      color-mix(in srgb, var(--app-primary) 10%, transparent) 0%,
      color-mix(in srgb, var(--app-info) 7%, transparent) 55%,
      transparent 100%
    ),
    var(--app-card-bg, #fff);
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
.hero__avatar--skeleton {
  margin: -44px 0 0 28px;
}
.hero__orb {
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 999px;
  right: 6%;
  top: -220px;
  background: color-mix(in srgb, var(--app-primary) 10%, transparent);
}
.hero__body {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 18px;
  padding: 96px 32px 20px;
  flex-wrap: wrap;
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}
.hero__avatar {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  object-fit: cover;
  border: 3px solid var(--app-card-bg, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 8%);
  margin-top: -56px;
  flex-shrink: 0;
  background: var(--app-muted-bg);
}
.hero__avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--app-text-secondary);
  font-size: 32px;
  font-weight: 800;
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
.pane-empty {
  padding: 56px 0;
}

/* 成员 / 申请：线条列表（分隔线行，无卡片边框） */
.member-grid {
  flex: 1;
  min-height: 0;
  grid-auto-rows: minmax(56px, auto);
  align-content: start;
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 0 48px;
}
.member-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-bottom: 1px solid var(--app-border);
  background: transparent;
  transition: background-color 0.15s ease;
}
.member-cell:hover {
  background: var(--app-muted-bg);
}
.member-cell__main {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.member-cell__name {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.member-cell__time {
  color: var(--app-text-secondary);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.member-cell__role {
  flex-shrink: 0;
}
.member-cell__actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* 分页钉底 */
.pane-pager {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}

/* 预留占位板块（垂直居中撑满） */
.module-placeholder {
  flex: 1;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  min-height: 280px;
}
.module-placeholder__icon {
  width: 72px;
  height: 72px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: var(--app-muted-bg);
  color: var(--app-text-secondary);
}
.module-placeholder__title {
  margin: 6px 0 0;
  font-size: 17px;
  font-weight: 700;
}
.module-placeholder__hint {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 13px;
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
    padding: 88px 16px 16px;
  }
  .hero__avatar {
    width: 72px;
    height: 72px;
    margin-top: -48px;
  }
  .module-tabs :deep(.n-tabs-nav),
  .module-tabs :deep(.n-tab-pane) {
    padding-left: 16px;
    padding-right: 16px;
  }
  .member-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
