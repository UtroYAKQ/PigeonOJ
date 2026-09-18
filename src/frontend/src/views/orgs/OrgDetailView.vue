<script setup lang="ts">
/**
 * 组织详情（/orgs/:id，docs/contracts/orgs.md）：组织空间式布局。
 * Hero（头像 + 名称 + 简介 + 动作区）+ 模块化内容区（tab 切换 + 数据装配）：
 * 成员 / 组织团队 / 组织题库，各模块面板见 ./components/*Panel.vue（面板自持列表数据）。
 * 权限按 my_role 显隐（org_admin ⊇ org_member）；非成员访问返回 2003，
 * 页面呈现无权访问态（组织无申请加入通道）；编辑 / 解散等组织级动作收敛在本组件。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Setting } from '@element-plus/icons-vue'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItem,
  NIcon,
  NInput,
  NSkeleton,
  NSpin,
  NTag,
} from 'naive-ui'

import { disbandOrg, getOrg, updateOrg } from '@/api/orgs'
import { uploadImage } from '@/api/files'
import { ApiError } from '@/api/http'
import BaseAvatar from '@/components/BaseAvatar.vue'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import OrgMembersPanel from './components/OrgMembersPanel.vue'
import OrgTeamsPanel from './components/OrgTeamsPanel.vue'
import OrgProblemsPanel from './components/OrgProblemsPanel.vue'
import type { OrgDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const orgId = String(route.params.id)
const org = ref<OrgDetail | null>(null)
const loadFailed = ref(false)
/** 403（非组织成员）标志：失败态下呈现无权访问提示而非裸错误 */
const forbidden = ref(false)
const loading = ref(false)

/** 组织管理员（org_admin；站点 admin 视同拥有全部组织管理权，docs/contracts/orgs.md） */
const isOrgAdmin = computed(() => org.value?.my_role === 'admin' || userStore.isAdmin)
/** 可见组织工作台（组织成员 my_role 非空；站点 admin 免成员校验） */
const isMember = computed(() => org.value?.my_role != null || userStore.isAdmin)
/** 站点 admin 且非组织成员：hero 显示站点管理员身份标签 */
const isSiteAdminViewer = computed(() => userStore.isAdmin && !org.value?.my_role)

/** 复制组织 ID（统计行）：显示前 8 位，复制完整 ID */
async function copyOrgId() {
  try {
    await navigator.clipboard.writeText(orgId)
    message.success(t('problems.detail.copied'))
  } catch {
    message.error(t('common.operationFailed'))
  }
}

// ---------------- 模块 tab（内容板块） ----------------

type OrgModule = 'members' | 'teams' | 'problems'
const activeModule = ref<OrgModule>('members')

const moduleMeta = computed(() => [
  { key: 'members' as OrgModule, labelKey: 'orgs.detail.tabMembers' },
  { key: 'teams' as OrgModule, labelKey: 'orgs.detail.tabTeams' },
  { key: 'problems' as OrgModule, labelKey: 'orgs.detail.tabProblems' },
])

// ---------------- 面板联动 ----------------

/** 成员移出 / 添加后：重拉组织概要（成员数等），面板已自行刷新列表 */
function onMembershipChanged() {
  void load()
}

// ---------------- 组织信息（编辑抽屉 / 解散） ----------------

const showSettings = ref(false)
const form = ref({ name: '', description: '', avatar_url: '' as string | null })
const saving = ref(false)
const uploadingAvatar = ref(false)

function openSettings() {
  if (!org.value) return
  form.value = {
    name: org.value.name,
    description: org.value.description ?? '',
    avatar_url: org.value.avatar_url ?? '',
  }
  showSettings.value = true
}

async function onAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingAvatar.value = true
  try {
    const result = await uploadImage(file)
    form.value.avatar_url = result.url
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploadingAvatar.value = false
    input.value = ''
  }
}

async function saveSettings() {
  if (!form.value.name.trim()) {
    message.warning(t('orgs.create.nameRequired'))
    return
  }
  saving.value = true
  try {
    org.value = await updateOrg(orgId, {
      name: form.value.name.trim(),
      description: form.value.description.trim() || undefined,
      avatar_url: form.value.avatar_url || undefined,
    })
    message.success(t('orgs.settings.saved'))
    showSettings.value = false
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

/** 解散组织（仅站点 admin；软解散，题库题目归档、授权全清） */
function onDisband() {
  confirmAsyncDialog({
    title: t('orgs.settings.disband'),
    content: t('orgs.settings.disbandConfirm'),
    positiveText: t('orgs.settings.disband'),
    action: async () => {
      await disbandOrg(orgId)
    },
    successMessage: t('orgs.settings.disbandSuccess'),
    onAfterSuccess: () => {
      void router.push('/me/orgs/mine')
    },
  })
}

// ---------------- 初始化 ----------------

async function load() {
  loading.value = true
  try {
    org.value = await getOrg(orgId)
    loadFailed.value = false
    forbidden.value = false
  } catch (error) {
    loadFailed.value = true
    // 2003 = 非组织成员（组织空间仅成员可访问）：呈现无权访问态
    forbidden.value = error instanceof ApiError && error.code === 2003
    message.error(error instanceof Error ? error.message : t('orgs.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <div class="org-fill">
      <!-- NSpin 只包 Hero（骨架 / 失败 / 信息），不参与模块卡的高度传导 -->
      <NSpin :show="loading" class="hero-spin">
        <!-- 加载骨架 -->
        <div v-if="!org && loading" class="hero hero--skeleton">
          <NSkeleton height="96px" :sharp="false" style="border-radius: 8px" />
          <NSkeleton text style="width: 30%" />
          <NSkeleton text style="width: 60%" />
        </div>

        <!-- 加载失败（403 = 非组织成员：无申请加入通道，仅提示） -->
        <div v-else-if="!org && loadFailed" class="hero hero--failed">
          <NEmpty
            :description="forbidden ? t('orgs.detail.forbidden') : t('orgs.detail.loadFailed')"
            size="large"
          >
            <template #extra>
              <NButton @click="load">{{ t('action.refresh') }}</NButton>
            </template>
          </NEmpty>
        </div>
      </NSpin>

      <!-- ======== Hero（不参与模块卡高度链） ======== -->
      <section v-if="org" class="hero">
        <div class="hero__banner" aria-hidden="true">
          <span class="hero__orb"></span>
          <span class="hero__ring"></span>
        </div>
        <BaseAvatar
          kind="team"
          :src="org.avatar_url"
          :name="org.name"
          :size="64"
          :round="false"
          :radius="10"
          class="hero__avatar"
        />
        <div class="hero__main">
          <div class="hero__title-row">
            <h1 class="hero__title">{{ org.name }}</h1>
            <NTag v-if="org.status === 'disbanded'" size="small" type="error" :bordered="false">
              {{ t('orgs.detail.statusDisbanded') }}
            </NTag>
            <NTag v-else-if="org.my_role" size="small" type="info" :bordered="false">
              {{ t(org.my_role === 'admin' ? 'orgs.role.admin' : 'orgs.role.member') }}
            </NTag>
            <NTag v-else-if="isSiteAdminViewer" size="small" type="warning" :bordered="false">
              {{ t('orgs.role.siteAdmin') }}
            </NTag>
          </div>
          <p class="hero__desc" :class="{ 'hero__desc--empty': !org.description }">
            {{ org.description ?? t('orgs.detail.descEmpty') }}
          </p>
          <!-- 统计行：成员数 / 团队数 / 创建时间 / 组织 ID（点击复制完整 ID） -->
          <div class="hero__meta">
            <span>
              {{ t('orgs.list.memberCount') }}
              <strong class="hero__meta-num">{{ org.member_count }}</strong>
            </span>
            <span class="hero__dot" aria-hidden="true">·</span>
            <span>
              {{ t('orgs.list.teamCount') }}
              <strong class="hero__meta-num">{{ org.team_count }}</strong>
            </span>
            <span class="hero__dot" aria-hidden="true">·</span>
            <span>{{ t('orgs.list.createdAt') }} {{ formatDateTime(org.created_at) }}</span>
            <span class="hero__dot" aria-hidden="true">·</span>
            <button
              type="button"
              class="hero__id"
              :title="t('orgs.detail.orgId')"
              @click="copyOrgId"
            >
              {{ t('orgs.detail.orgId') }} {{ orgId.slice(0, 8) }}
            </button>
          </div>
        </div>

        <!-- 动作区：org_admin 编辑信息；站点 admin 解散组织 -->
        <div class="hero__actions">
          <NButton v-if="isOrgAdmin" secondary size="large" @click="openSettings">
            <template #icon>
              <NIcon :component="Setting" />
            </template>
            {{ t('orgs.detail.editInfo') }}
          </NButton>
          <NButton v-if="userStore.isAdmin" type="error" secondary size="large" @click="onDisband">
            {{ t('orgs.settings.disband') }}
          </NButton>
        </div>
      </section>

      <!-- ======== 内容模块（tab 线条直连内容） ======== -->
      <section v-if="org" class="module-area">
        <n-tabs v-model:value="activeModule" type="line" class="module-tabs">
          <n-tab-pane
            v-for="moduleItem in moduleMeta"
            :key="moduleItem.key"
            :name="moduleItem.key"
            :tab="t(moduleItem.labelKey)"
            display-directive="show"
          >
            <!-- 成员 -->
            <OrgMembersPanel
              v-if="moduleItem.key === 'members'"
              :org-id="orgId"
              :is-org-admin="isOrgAdmin"
              :is-member="isMember"
              @changed="onMembershipChanged"
            />

            <!-- 组织团队 -->
            <OrgTeamsPanel
              v-else-if="moduleItem.key === 'teams'"
              :org-id="orgId"
              :is-org-admin="isOrgAdmin"
            />

            <!-- 组织题库 -->
            <OrgProblemsPanel v-else :org-id="orgId" :is-member="isMember" />
          </n-tab-pane>
        </n-tabs>
      </section>
    </div>

    <!-- 编辑信息抽屉（org_admin） -->
    <NDrawer v-model:show="showSettings" :width="440" placement="right">
      <NDrawerContent :title="t('orgs.settings.infoTitle')" closable>
        <NForm label-placement="top">
          <NFormItem :label="t('orgs.create.name')" required>
            <NInput v-model:value="form.name" maxlength="64" />
          </NFormItem>
          <NFormItem :label="t('orgs.create.description')">
            <NInput v-model:value="form.description" type="textarea" :rows="4" maxlength="2000" />
          </NFormItem>
          <NFormItem :label="t('orgs.settings.avatar')">
            <div class="avatar-uploader">
              <div class="avatar-preview" :class="{ empty: !form.avatar_url }">
                <img v-if="form.avatar_url" :src="form.avatar_url" alt="" />
                <span v-else>{{ t('orgs.settings.noAvatar') }}</span>
              </div>
              <label class="avatar-upload-btn">
                <input type="file" accept="image/*" hidden @change="onAvatarChange" />
                <NButton size="small" :loading="uploadingAvatar" tag="span">
                  {{ t('orgs.settings.avatar') }}
                </NButton>
              </label>
              <span class="field-hint">{{ t('contests.list.logoHint') }}</span>
            </div>
          </NFormItem>
        </NForm>
        <template #footer>
          <div class="modal-actions">
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
   通铺布局：抵消应用壳卡片默认 padding，内容直接铺满（同团队详情）
   ============================================================ */
.org-fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin: calc(-1 * var(--n-padding-top, 20px)) calc(-1 * var(--n-padding-left, 24px))
    calc(-1 * var(--n-padding-bottom, 24px));
}

/* ======== Hero：中性底，简洁单行 ======== */
.hero {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 24px 32px 20px;
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
  flex-wrap: wrap;
  overflow: hidden;
}
/* Hero 装饰（与团队工作台同款：圆弧 + 描边环，见 TeamDetailView） */
.hero__banner {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
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
.hero__ring {
  position: absolute;
  width: 228px;
  height: 228px;
  border-radius: 999px;
  right: -104px;
  bottom: -120px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 24%, transparent);
}
.hero--skeleton {
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
.hero__avatar {
  position: relative;
  border: 3px solid var(--app-card-bg, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 8%);
}
.hero__main {
  position: relative;
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
.hero__actions {
  position: relative;
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

/* 弹窗 / 抽屉底部动作区 */
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.field-hint {
  color: var(--app-text-secondary);
  font-size: 12px;
  margin: 0;
}

/* 头像上传（编辑抽屉，同团队设置） */
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

@media (max-width: 860px) {
  .hero {
    padding: 20px 16px;
  }
  .hero__actions {
    margin-left: 0;
    width: 100%;
  }
  .hero__avatar {
    width: 56px;
    height: 56px;
  }
  .module-tabs :deep(.n-tabs-nav),
  .module-tabs :deep(.n-tab-pane) {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
