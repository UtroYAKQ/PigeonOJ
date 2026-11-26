<script setup lang="ts">
/**
 * 题解编辑页（新建 / 编辑复用）：标题 + MarkdownEditor（KaTeX / 图片上传随全局）。
 * 「发布」与「存草稿」双动作；编辑已发布题解隐藏存草稿（不做发布态降级）。
 * 表单页不进 KeepAlive（frontend.md 缓存约定），进出重新挂载保证数据新鲜。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { createSolution, getSolution, updateSolution } from '@/api/community'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import type { SolutionDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const problemId = computed(() => String(route.params.problemId ?? route.params.id))
const solutionId = computed(() => (route.params.solutionId ? String(route.params.solutionId) : ''))
const isEdit = computed(() => Boolean(solutionId.value))
const problemPath = computed(() => {
  if (route.params.orgId) {
    return `/me/orgs/${String(route.params.orgId)}/problems/${problemId.value}`
  }
  if (route.params.setId) {
    return `/problem-sets/${String(route.params.setId)}/problems/${problemId.value}`
  }
  if (route.params.cid) {
    return `/contests/${String(route.params.cid)}/problems/${problemId.value}`
  }
  return `/problems/${problemId.value}`
})
const solutionsBase = computed(() => `${problemPath.value}/solutions`)

const title = ref('')
const content = ref('')
const loading = ref(false)
const saving = ref(false)
/** 未登录 / 非作者直接离开（编辑态加载后校验） */
const blocked = ref(false)

async function load() {
  if (!isEdit.value) {
    // 新建：未登录直接拦截（按钮入口已挡，兜底手输 URL）
    if (!userStore.isLoggedIn) {
      message.warning(t('problems.solutions.loginRequired'))
      blocked.value = true
      return
    }
    return
  }
  loading.value = true
  try {
    const detail: SolutionDetail = await getSolution(solutionId.value)
    if (detail.author.id !== userStore.user?.id) {
      message.warning(t('problems.solutions.notOwner'))
      blocked.value = true
      return
    }
    if (detail.status === 'removed') {
      message.warning(t('problems.solutions.removedLocked'))
      blocked.value = true
      return
    }
    title.value = detail.title
    content.value = detail.content
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
    blocked.value = true
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!title.value.trim()) {
    message.warning(t('problems.solutions.titleRequired'))
    return
  }
  if (!content.value.trim()) {
    message.warning(t('problems.solutions.contentRequired'))
    return
  }
  saving.value = true
  try {
    const payload = { title: title.value.trim(), content: content.value }
    if (isEdit.value) {
      await updateSolution(solutionId.value, payload)
    } else {
      await createSolution(problemId.value, payload)
    }
    message.success(t('common.success'))
    void router.replace(solutionsBase.value)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  } finally {
    saving.value = false
  }
}

function goBack() {
  void router.push(solutionsBase.value)
}

onMounted(load)
</script>

<template>
  <WorkbenchShell
    :title="isEdit ? t('problems.solutions.editTitle') : t('problems.solutions.createTitle')"
  >
    <template #header-extra>
      <n-button secondary :disabled="saving" @click="goBack">
        {{ t('action.cancel') }}
      </n-button>
    </template>

    <n-spin
      :show="loading || saving"
      class="table-fill"
      content-style="height: 100%; overflow: auto"
    >
      <div v-show="!blocked" class="solution-editor">
        <div class="solution-editor__field">
          <label class="solution-editor__label">{{ t('problems.solutions.titleLabel') }}</label>
          <n-input
            v-model:value="title"
            maxlength="255"
            show-count
            :placeholder="t('problems.solutions.titlePlaceholder')"
          />
        </div>
        <div class="solution-editor__field solution-editor__field--grow">
          <label class="solution-editor__label">{{ t('problems.solutions.contentLabel') }}</label>
          <MarkdownEditor
            v-model="content"
            :placeholder="t('problems.solutions.contentPlaceholder')"
            min-height="480px"
          />
        </div>
        <div class="solution-editor__actions">
          <n-button type="primary" :loading="saving" @click="save()">
            {{ t('problems.solutions.publish') }}
          </n-button>
        </div>
      </div>
    </n-spin>
    <div v-show="blocked && !loading" class="table-fill-empty solution-editor__empty">
      {{ t('common.loadFailed') }}
    </div>
  </WorkbenchShell>
</template>

<style scoped>
.solution-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.solution-editor__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.solution-editor__field--grow {
  flex: 1;
  min-height: 0;
}
/* MarkdownEditor 以 min-height 定高（minHeight prop），随内容行数撑开编辑区 */
.solution-editor__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
}
.solution-editor__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 4px 0;
}
.solution-editor__empty {
  color: var(--app-text-secondary);
}
</style>
