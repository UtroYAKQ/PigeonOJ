<script setup lang="ts">
/**
 * 团队中心：我的团队卡片墙（分页）+ 创建团队（admin/tutor）。
 * 卡片范式与比赛列表（ContestListView）一致：单行头部（头像 + 名称 + 右侧角色点标）、
 * 描述两行截断、成员数元信息、底部创建时间；
 * 悬停仅边框加深 + 标题主色，无位移 / 阴影 / 动画。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { CirclePlus } from '@element-plus/icons-vue'
import { NButton, NIcon } from 'naive-ui'

import { createTeam, listMyTeams } from '@/api/teams'
import { message } from '@/utils/feedback'
import { useUserStore } from '@/stores/user'
import { usePagination } from '@/composables/usePagination'
import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import { formatDateTime } from '@/utils/format'
import type { TeamRoleType, TeamSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const canCreate = computed(() => userStore.hasAnyRole(['admin', 'tutor']))

const loading = ref(false)
const list = ref<TeamSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage } = usePagination()
const keyword = ref('')

const showCreate = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', description: '' })

/** 我的角色 → 点标（语义色 class + 文案 key；创建者警示橙 / 管理员信息蓝 / 成员中性灰） */
const roleMeta: Record<TeamRoleType, { cls: string; labelKey: string }> = {
  creator: { cls: 'role-chip--creator', labelKey: 'teams.role.creator' },
  admin: { cls: 'role-chip--admin', labelKey: 'teams.role.admin' },
  member: { cls: 'role-chip--member', labelKey: 'teams.role.member' },
}

function initialOf(team: TeamSummary) {
  return team.name?.trim()?.charAt(0).toUpperCase() || 'T'
}

async function load() {
  loading.value = true
  try {
    const result = await listMyTeams({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    list.value = result.items
    total.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('teams.list.loadFailed'))
  } finally {
    loading.value = false
  }
}

function onSearch() {
  resetPage()
  load()
}

function openTeam(team: TeamSummary) {
  void router.push(`/teams/${team.id}`)
}

async function doCreate() {
  if (!createForm.value.name.trim()) {
    message.warning(t('teams.create.nameRequired'))
    return
  }
  creating.value = true
  try {
    const team = await createTeam({
      name: createForm.value.name.trim(),
      description: createForm.value.description.trim() || undefined,
    })
    message.success(t('teams.create.success'))
    showCreate.value = false
    createForm.value = { name: '', description: '' }
    void router.push(`/teams/${team.id}`)
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
      :placeholder="t('teams.list.search')"
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
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
        <n-button v-if="canCreate" type="primary" @click="showCreate = true">
          <template #icon>
            <n-icon :component="CirclePlus" />
          </template>
          {{ t('teams.list.create') }}
        </n-button>
      </template>
    </SearchFilterBar>

    <!-- 与题库 / 题单（PaginatedDataTable）同构：spin 只渲染卡片墙（全局类 table-fill 吃满），
         空态为其兄弟节点、用全局类 table-fill-empty 拉伸居中；
         v-show 而非 v-if（分支锚点增删会触发 Vue patch 崩溃，同 PaginatedDataTable 注释） -->
    <n-spin
      v-show="loading || list.length"
      :show="loading"
      class="table-fill"
      content-style="height: 100%; overflow: auto"
    >
      <div class="cards">
        <article
          v-for="team in list"
          :key="team.id"
          class="team-card"
          role="button"
          tabindex="0"
          @click="openTeam(team)"
          @keyup.enter="openTeam(team)"
        >
          <div class="team-card__top">
            <img v-if="team.avatar_url" :src="team.avatar_url" alt="" class="team-card__avatar" />
            <div
              v-else
              class="team-card__avatar team-card__avatar--fallback"
              aria-hidden="true"
            >
              {{ initialOf(team) }}
            </div>
            <h3 class="team-card__title" :title="team.name">{{ team.name }}</h3>
            <span
              v-if="team.my_role"
              class="role-chip"
              :class="roleMeta[team.my_role].cls"
            >
              <span class="role-chip__dot" aria-hidden="true" />
              {{ t(roleMeta[team.my_role].labelKey) }}
            </span>
          </div>

          <p class="team-card__desc" :class="{ 'team-card__desc--empty': !team.description }">
            {{ team.description ?? '—' }}
          </p>

          <div class="team-card__meta">
            <span class="team-card__count">
              {{ t('teams.list.memberCount') }}
              <strong>{{ team.member_count }}</strong>
            </span>
          </div>

          <div class="team-card__footer">
            <span>{{ formatDateTime(team.created_at) }}</span>
          </div>
        </article>
      </div>
    </n-spin>
    <div v-show="!loading && !list.length" class="table-fill-empty">
      <n-empty size="large" :description="t('teams.list.empty')" />
    </div>

    <div v-if="total > 0" class="pager">
      <span class="pager__total">{{ t('teams.list.totalCount', { count: total }) }}</span>
      <div class="pager__spacer" />
      <n-pagination
        :page="page"
        :page-size="pageSize"
        :item-count="total"
        :page-sizes="[12, 24, 48]"
        show-size-picker
        @update:page="
          (p: number) => {
            changePage(p)
            load()
          }
        "
        @update:page-size="
          (s: number) => {
            changeSize(s)
            load()
          }
        "
      />
    </div>

    <n-modal
      v-model:show="showCreate"
      :title="t('teams.list.create')"
      preset="card"
      style="width: 480px"
    >
      <n-form label-placement="top">
        <n-form-item :label="t('teams.create.name')" required>
          <n-input
            v-model:value="createForm.name"
            maxlength="64"
            :placeholder="t('teams.create.namePlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('teams.create.description')">
          <n-input
            v-model:value="createForm.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            :placeholder="t('teams.create.descriptionPlaceholder')"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-actions">
          <n-button @click="showCreate = false">{{ t('action.cancel') }}</n-button>
          <n-button type="primary" :loading="creating" @click="doCreate">
            {{ t('action.save') }}
          </n-button>
        </div>
      </template>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
/* 空态与高度链由全局类 table-fill / table-fill-empty 承载（main.css），
   与题库 / 题单列表同一机制 */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  min-height: 240px;
  align-content: start;
}

/* ---- 团队卡片：单行头部（头像 + 名称 + 右侧角色点标），纯平面极简 ---- */
.team-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 20px 18px;
  border: 1px solid var(--app-border);
  background: var(--app-card-bg, #fff);
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.team-card:hover {
  border-color: var(--app-text-muted);
}
.team-card:hover .team-card__title {
  color: var(--app-primary);
}
.team-card:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: 2px;
}
.team-card__top {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.team-card__avatar {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--app-border);
  flex-shrink: 0;
}
.team-card__avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-muted-bg);
  border: 1px solid var(--app-border);
  color: var(--app-text-secondary);
  font-size: 16px;
  font-weight: 650;
}
.team-card__title {
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
/* 角色 = 色点 + 文本（不单一靠颜色，文本承载语义）；创建者 / 管理员 / 成员三级 */
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
.role-chip--creator {
  color: var(--app-warning);
}
.role-chip--creator .role-chip__dot {
  background: var(--app-warning);
}
.role-chip--admin {
  color: var(--app-info);
}
.role-chip--admin .role-chip__dot {
  background: var(--app-info);
}
/* 描述固定两行高度：无描述也占位，保证同排卡片底部对齐 */
.team-card__desc {
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
.team-card__desc--empty {
  opacity: 0.55;
}
.team-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.team-card__count strong {
  color: var(--app-primary);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-left: 2px;
}
.team-card__footer {
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
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}
.pager__spacer {
  flex: 1;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
@media (max-width: 700px) {
  .pager {
    justify-content: center;
  }
}
</style>
