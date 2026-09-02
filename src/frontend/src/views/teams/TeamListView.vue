<script setup lang="ts">
/**
 * 团队中心：我的团队卡片墙（分页）+ 创建团队（admin/tutor）。
 * 卡片范式与比赛列表（ContestListView）一致：头像左上 / 角色徽标右上 /
 * 名称其下 / 描述两行截断 / 元信息与底部引导收尾；团队基础管理在 /teams/:id。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { CirclePlus } from '@element-plus/icons-vue'
import { NButton, NIcon, NTag } from 'naive-ui'

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

/** 我的角色 → 徽标（颜色与文案；创建者警示橙 / 管理员信息蓝 / 成员中性灰） */
const roleMeta: Record<TeamRoleType, { type: 'warning' | 'info' | 'default'; labelKey: string }> = {
  creator: { type: 'warning', labelKey: 'teams.role.creator' },
  admin: { type: 'info', labelKey: 'teams.role.admin' },
  member: { type: 'default', labelKey: 'teams.role.member' },
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

// 角色徽标渲染（模板内以组件方式复用）
const RoleBadge = (props: { role: TeamRoleType }) => {
  const meta = roleMeta[props.role]
  return h(
    NTag,
    { size: 'small', round: true, bordered: false, type: meta.type },
    { default: () => t(meta.labelKey) },
  )
}

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.teams')">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('teams.list.search')"
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

    <n-spin :show="loading" class="cards-fill">
      <div v-if="list.length" class="cards">
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
            <div v-else class="team-card__avatar team-card__avatar--fallback" aria-hidden="true">
              {{ initialOf(team) }}
            </div>
            <div class="team-card__badges">
              <RoleBadge v-if="team.my_role" :role="team.my_role" />
            </div>
          </div>

          <h3 class="team-card__title" :title="team.name">{{ team.name }}</h3>
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
            <span class="team-card__spacer" aria-hidden="true"></span>
            <span class="team-card__enter">{{ t('teams.list.enter') }}</span>
            <span class="team-card__arrow" aria-hidden="true">→</span>
          </div>
        </article>
      </div>
      <div v-else-if="!loading" class="cards-empty">
        <n-empty size="large" :description="t('teams.list.empty')">
          <template #extra>
            <n-button v-if="canCreate" type="primary" size="small" @click="showCreate = true">
              {{ t('teams.list.create') }}
            </n-button>
          </template>
        </n-empty>
      </div>
    </n-spin>

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
/* 视口锁定高度链：page-fill 的直接子元素需吃满剩余高度，分页器才能钉底 */
.cards-fill {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.cards-fill :deep(.n-spin-container),
.cards-fill :deep(.n-spin-content) {
  height: 100%;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 18px;
  min-height: 240px;
  align-content: start;
}
.cards-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

/* ---- 团队卡片：头像左上 / 角色徽标右上 / 名称其下 / 描述两行截断 /
        成员数元信息 / 虚线footer（创建时间 + 进入引导） ---- */
.team-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-card-bg, #fff);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}
.team-card:hover {
  border-color: var(--app-primary);
  box-shadow: 0 4px 14px rgb(0 0 0 / 6%);
}
.team-card:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: 2px;
}
.team-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.team-card__avatar {
  width: 52px;
  height: 52px;
  border-radius: 10px;
  object-fit: cover;
  border: 1px solid var(--app-border);
  flex-shrink: 0;
}
.team-card__avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-muted-bg);
  color: var(--app-text-secondary);
  font-size: 20px;
  font-weight: 700;
}
.team-card__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.team-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  line-height: 1.35;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 描述固定两行高度：无描述也占位，保证同排卡片底部对齐 */
.team-card__desc {
  margin: -4px 0 0;
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
  color: var(--app-text-secondary);
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
  border-top: 1px dashed var(--app-border);
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}
.team-card__spacer {
  flex: 1;
}
/* 进入引导：悬停时主色点亮，暗示可点击 */
.team-card__enter {
  font-weight: 600;
  letter-spacing: 0.3px;
  opacity: 0.65;
  transition: opacity 0.18s ease;
}
.team-card__arrow {
  opacity: 0.55;
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}
.team-card:hover .team-card__enter {
  opacity: 1;
  color: var(--app-primary);
}
.team-card:hover .team-card__arrow {
  opacity: 1;
  color: var(--app-primary);
  transform: translateX(2px);
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
