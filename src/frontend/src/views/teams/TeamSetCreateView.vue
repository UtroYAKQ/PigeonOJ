<script setup lang="ts">
/**
 * 团队题单创建页（/teams/:teamId/sets/new）：双框工作台（与管理后台创建页同形态）。
 * 左框「基本信息」：标题 + 可选「从我的题单复制」（快照复制本人全站题单条目，
 * 仅 tutor / admin 全局身份可见，docs/contracts/teams.md 团队空间节）；
 * 右框「题单说明」：Markdown 编辑器撑满。成功后 replace 回团队详情。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { FormInst, FormRules } from 'naive-ui'

import { createTeamProblemSet } from '@/api/teams'
import { listProblemSets } from '@/api/problemSets'
import { message } from '@/utils/feedback'
import { useUserStore } from '@/stores/user'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { ProblemSetSummary } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const teamId = String(route.params.teamId)

/** 复制能力：tutor / admin 才拥有可复制的本人全站题单 */
const canCopy = computed(() => userStore.hasAnyRole(['admin', 'tutor']))

const submitting = ref(false)

const formRef = ref<FormInst | null>(null)
const form = reactive({
  title: '',
  description: '',
  copyFromSetId: null as string | null,
  visibility: 'team_visible' as 'team_visible' | 'admin_visible',
})

const rules: FormRules = {
  title: [
    { required: true, message: t('teams.space.setTitleRequired'), trigger: ['blur', 'input'] },
  ],
}

/** 可复制来源：本人未下线的全站题单（团队题单已在团队空间内） */
const mySets = ref<ProblemSetSummary[]>([])
const mySetsLoading = ref(false)

const copyOptions = computed(() =>
  mySets.value.map((it) => ({
    label: `${it.title}（${it.item_count} 题）`,
    value: it.id,
  })),
)

function backToTeam() {
  void router.replace(`/teams/${teamId}`)
}

async function loadMySets() {
  mySetsLoading.value = true
  try {
    const result = await listProblemSets({ page: 1, page_size: 50, mine: true })
    mySets.value = result.items.filter(
      (it) => it.visibility === 'public' || it.visibility === 'private',
    )
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    mySetsLoading.value = false
  }
}

async function submitCreate() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    await createTeamProblemSet(teamId, {
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      copy_from_set_id: form.copyFromSetId ?? undefined,
      visibility: form.visibility,
    })
    message.success(t('teams.space.setCreated'))
    backToTeam()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  if (canCopy.value) void loadMySets()
})
</script>

<template>
  <WorkbenchShell :title="t('teams.space.createSet')">
    <template #header-extra>
      <div class="form-actions">
        <n-button size="small" :disabled="submitting" @click="backToTeam">
          {{ t('action.cancel') }}
        </n-button>
        <n-button type="primary" size="small" :loading="submitting" @click="submitCreate">
          {{ t('action.save') }}
        </n-button>
      </div>
    </template>

    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" class="form-grid">
      <!-- 左框：基本信息（标题 + 复制来源 + 提示） -->
      <section class="panel">
        <div class="panel__head">
          <span>{{ t('problemSets.form.basicTitle') }}</span>
        </div>
        <div class="panel__body panel__body--scroll">
          <n-form-item :label="t('problemSets.list.titleLabel')" path="title">
            <n-input
              v-model:value="form.title"
              size="large"
              :maxlength="128"
              show-count
              :placeholder="t('teams.space.setTitleRequired')"
            />
          </n-form-item>
          <n-form-item :label="t('problemSets.form.visibility')" :show-feedback="false">
            <n-radio-group v-model:value="form.visibility">
              <n-radio value="team_visible">{{ t('teams.space.teamVisible') }}</n-radio>
              <n-radio value="admin_visible">{{ t('teams.space.adminVisible') }}</n-radio>
            </n-radio-group>
          </n-form-item>
          <p class="form-tip">{{ t('teams.space.setVisibilityHint') }}</p>
          <template v-if="canCopy">
            <n-form-item :label="t('teams.space.copyFromSet')" :show-feedback="false">
              <n-select
                v-model:value="form.copyFromSetId"
                :options="copyOptions"
                :loading="mySetsLoading"
                clearable
                :placeholder="t('teams.space.copyFromSetPlaceholder')"
              />
            </n-form-item>
            <p class="form-tip">{{ t('teams.space.copyFromSetHint') }}</p>
          </template>
        </div>
        <div class="panel__foot"></div>
      </section>

      <!-- 右框：题单说明（Markdown 编辑器撑满） -->
      <section class="panel">
        <div class="panel__head">
          <span>{{ t('problemSets.list.descLabel') }}</span>
        </div>
        <div class="panel__body panel__body--flush">
          <div class="editor-fill">
            <MarkdownEditor
              v-model="form.description"
              min-height="420px"
              :placeholder="t('problemSets.form.descPlaceholder')"
            />
          </div>
        </div>
      </section>
    </n-form>
  </WorkbenchShell>
</template>

<style scoped>
.form-actions {
  display: inline-flex;
  gap: 8px;
}
/* 左 4 右 8 两个等高面板框（与管理后台创建页同款）：grid stretch 对齐，
   锁定行高不撑破视口，超出交给框内滚动 */
.form-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 8fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 20px;
  padding-top: 4px;
}
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background: var(--app-card-bg);
  overflow: hidden;
}
.panel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding: 12px 20px 8px;
  font-size: 14px;
  font-weight: 600;
}
.panel__body {
  flex: 1;
  min-height: 0;
}
.panel__body--scroll {
  overflow: auto;
  padding: 4px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.panel__body--flush {
  display: flex;
  flex-direction: column;
  padding: 12px;
}
/* 编辑器填充容器：md-editor-v3 以内联 style 设固定高度，绝对定位铺满父级 */
.editor-fill {
  position: relative;
  flex: 1;
  min-height: 420px;
}
.editor-fill :deep(.md-editor-shell) {
  position: absolute;
  inset: 0;
  height: auto !important;
}
.form-tip {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.panel__foot {
  flex-shrink: 0;
  padding: 10px 20px 14px;
}
@media (max-width: 900px) {
  /* 窄屏：单列自然高度，编辑器以 min-height 420 兜底 */
  .form-grid {
    flex: none;
    grid-template-columns: 1fr;
    grid-template-rows: none;
  }
  .panel__body--scroll {
    overflow: visible;
  }
}
</style>
