<script setup lang="ts">
/**
 * 组织中心（/orgs/mine，docs/contracts/orgs.md）：
 * 我的组织列表（GET /orgs/mine，卡片墙，带成员数 / 团队数 / 我的角色），
 * 站点 admin 可见「创建组织」入口（POST /orgs，可不带初始管理员，后续在详情中任命）。
 * 卡片范式与团队中心（TeamListView）一致。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { CirclePlus } from '@element-plus/icons-vue'

import { createOrg, listMyOrgs } from '@/api/orgs'
import { useUserStore } from '@/stores/user'
import BaseAvatar from '@/components/BaseAvatar.vue'
import ModalFooter from '@/components/ModalFooter.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import type { OrgRoleType, OrgSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const loading = ref(false)
const list = ref<OrgSummary[]>([])
const { page, pageSize, total, changePage, resetPage } = usePagination()
const keyword = ref('')

/** 我的角色 → 点标（语义色 class + 文案 key；组织管理员信息蓝 / 成员中性灰） */
const roleMeta: Record<OrgRoleType, { cls: string; labelKey: string }> = {
  admin: { cls: 'role-chip--admin', labelKey: 'orgs.role.admin' },
  member: { cls: 'role-chip--member', labelKey: 'orgs.role.member' },
}

async function load() {
  loading.value = true
  try {
    const result = await listMyOrgs({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    list.value = result.items
    total.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('orgs.list.loadFailed'))
  } finally {
    loading.value = false
  }
}

function onSearch() {
  resetPage()
  load()
}

function openOrg(org: OrgSummary) {
  void router.push(`/me/orgs/${org.id}`)
}

// ---- 创建组织（仅站点 admin；可不带初始管理员，组织管理员可在详情中任命） ----

const showCreate = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', description: '' })

function openCreate() {
  createForm.value = { name: '', description: '' }
  showCreate.value = true
}

async function doCreate() {
  if (!createForm.value.name.trim()) {
    message.warning(t('orgs.create.nameRequired'))
    return
  }
  creating.value = true
  try {
    const org = await createOrg({
      name: createForm.value.name.trim(),
      description: createForm.value.description.trim() || undefined,
    })
    message.success(t('orgs.create.success'))
    showCreate.value = false
    void router.push(`/me/orgs/${org.id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('orgs.list.search')"
      search-width="300px"
      @update:keyword="
        (v: string) => {
          keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <n-button v-if="userStore.isAdmin" type="primary" size="small" @click="openCreate">
          <template #icon>
            <n-icon :component="CirclePlus" />
          </template>
          {{ t('orgs.create.title') }}
        </n-button>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <!-- 与团队中心同一分页组件（PaginatedDataTable）：卡片墙经 #content 注入 -->
    <PaginatedDataTable
      :data="list"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t('orgs.list.empty')"
      @update:page="
        (p: number) => {
          changePage(p)
          load()
        }
      "
    >
      <template #content>
        <n-spin
          v-show="loading || list.length"
          :show="loading"
          class="table-fill"
          content-style="height: 100%; overflow: auto"
        >
          <div class="cards">
            <article
              v-for="org in list"
              :key="org.id"
              class="org-card"
              role="button"
              tabindex="0"
              @click="openOrg(org)"
              @keyup.enter="openOrg(org)"
            >
              <div class="org-card__top">
                <BaseAvatar
                  kind="team"
                  :src="org.avatar_url"
                  :name="org.name"
                  :size="40"
                  :round="false"
                  :radius="8"
                  bordered
                />
                <h3 class="org-card__title" :title="org.name">{{ org.name }}</h3>
                <span v-if="org.my_role" class="role-chip" :class="roleMeta[org.my_role].cls">
                  <span class="role-chip__dot" aria-hidden="true" />
                  {{ t(roleMeta[org.my_role].labelKey) }}
                </span>
              </div>

              <p class="org-card__desc" :class="{ 'org-card__desc--empty': !org.description }">
                {{ org.description ?? '—' }}
              </p>

              <div class="org-card__meta">
                <span>
                  {{ t('orgs.list.memberCount') }}
                  <strong>{{ org.member_count }}</strong>
                </span>
                <span class="org-card__sep" aria-hidden="true">·</span>
                <span>
                  {{ t('orgs.list.teamCount') }}
                  <strong>{{ org.team_count }}</strong>
                </span>
              </div>

              <div class="org-card__footer">
                <span>{{ t('orgs.list.createdAt') }} {{ formatDateTime(org.created_at) }}</span>
              </div>
            </article>
          </div>
        </n-spin>
      </template>
      <template #pager-left>
        <span class="pager__total">{{ t('orgs.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>

    <!-- 创建组织（仅站点 admin；初始管理员可留空，后续在详情中任命） -->
    <n-modal
      v-model:show="showCreate"
      :title="t('orgs.create.title')"
      preset="card"
      style="width: 480px"
    >
      <n-form label-placement="top">
        <n-form-item :label="t('orgs.create.name')" required>
          <n-input
            v-model:value="createForm.name"
            maxlength="64"
            :placeholder="t('orgs.create.namePlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('orgs.create.description')">
          <n-input
            v-model:value="createForm.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            :placeholder="t('orgs.create.descriptionPlaceholder')"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <ModalFooter
          :loading="creating"
          :confirm-text="t('action.save')"
          @cancel="showCreate = false"
          @confirm="doCreate"
        />
      </template>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
/* 空态与高度链由全局类 table-fill / table-fill-empty 承载（main.css），与团队中心同一机制 */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  min-height: 240px;
  align-content: start;
}

/* ---- 组织卡片：与团队卡片同范式（平面方角、纯 1px 边框） ---- */
.org-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 20px 18px;
  border: 1px solid var(--app-border);
  background: var(--app-card-bg, #fff);
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.org-card:hover {
  border-color: var(--app-text-muted);
}
.org-card:hover .org-card__title {
  color: var(--app-primary);
}
.org-card:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: 2px;
}
.org-card__top {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.org-card__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s ease;
}
/* 角色 = 色点 + 文本（不单一靠颜色传递状态） */
.role-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  font-size: 11px;
  line-height: 1;
  color: var(--app-text-secondary);
}
.role-chip__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--app-text-muted);
}
.role-chip--admin {
  color: var(--app-info);
}
.role-chip--admin .role-chip__dot {
  background: var(--app-info);
}
.org-card__desc {
  margin: 0;
  min-height: 37px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.org-card__desc--empty {
  opacity: 0.55;
}
.org-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}
.org-card__meta strong {
  color: var(--app-primary);
  font-weight: 700;
  margin-left: 2px;
}
.org-card__sep {
  opacity: 0.45;
}
.org-card__footer {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid var(--app-border);
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
