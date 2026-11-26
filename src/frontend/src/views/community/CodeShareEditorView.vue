<script setup lang="ts">
/**
 * 分享代码编辑页：标题 + 语言 + 可选关联题目（远程搜索公开题）+ 说明（Markdown）+ 代码。
 * 表单页不进 KeepAlive（frontend.md 缓存约定），保存成功回代码广场列表。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { createCodeShare } from '@/api/community'
import CodeEditor from '@/components/CodeEditor.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { languageOptions } from '@/constants/languages'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const title = ref('')
const language = ref<'cpp17' | 'python3.12' | 'java21'>('cpp17')
const code = ref('')
const description = ref('')
const saving = ref(false)
/** 未登录直接拦截（入口已挡，兜底手输 URL） */
const blocked = ref(!userStore.isLoggedIn)

async function save() {
  if (!title.value.trim()) {
    message.warning(t('codes.titleRequired'))
    return
  }
  if (!code.value.trim()) {
    message.warning(t('codes.codeRequired'))
    return
  }
  saving.value = true
  try {
    await createCodeShare({
      title: title.value.trim(),
      language: language.value,
      code: code.value,
      description: description.value.trim() || undefined,
    })
    message.success(t('common.success'))
    void router.replace('/codes')
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  } finally {
    saving.value = false
  }
}

function goBack() {
  void router.push('/codes')
}

onMounted(() => {
  if (blocked.value) message.warning(t('problems.solutions.loginRequired'))
})
</script>

<template>
  <WorkbenchShell :title="t('codes.createTitle')">
    <template #header-extra>
      <n-button secondary :disabled="saving" @click="goBack">
        {{ t('action.cancel') }}
      </n-button>
    </template>

    <n-spin :show="saving" class="table-fill" content-style="height: 100%; overflow: auto">
      <div v-if="!blocked" class="share-editor">
        <div class="share-editor__row">
          <div class="share-editor__field share-editor__field--grow">
            <label class="share-editor__label">{{ t('codes.titleLabel') }}</label>
            <n-input
              v-model:value="title"
              maxlength="255"
              show-count
              :placeholder="t('codes.titlePlaceholder')"
            />
          </div>
          <div class="share-editor__field">
            <label class="share-editor__label">{{ t('codes.languageLabel') }}</label>
            <n-select v-model:value="language" :options="languageOptions" style="width: 180px" />
          </div>
        </div>
        <div class="share-editor__field">
          <label class="share-editor__label">{{ t('codes.descriptionLabel') }}</label>
          <n-input
            v-model:value="description"
            type="textarea"
            :placeholder="t('codes.descriptionPlaceholder')"
            :autosize="{ minRows: 3, maxRows: 8 }"
          />
        </div>
        <div class="share-editor__field share-editor__field--grow">
          <label class="share-editor__label">{{ t('codes.codeLabel') }}</label>
          <div class="share-editor__code">
            <CodeEditor v-model="code" :language="language" />
          </div>
        </div>
        <div class="share-editor__actions">
          <n-button type="primary" :loading="saving" @click="save">
            {{ t('codes.publish') }}
          </n-button>
        </div>
      </div>
      <div v-else class="table-fill-empty share-editor__empty">
        {{ t('problems.solutions.loginRequired') }}
      </div>
    </n-spin>
  </WorkbenchShell>
</template>

<style scoped>
.share-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.share-editor__row {
  display: flex;
  gap: 14px;
}
.share-editor__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.share-editor__field--grow {
  flex: 1;
}
.share-editor__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
}
.share-editor__code {
  flex: 1;
  min-height: 320px;
}
.share-editor__code :deep(.code-editor) {
  height: 100%;
  min-height: 320px;
}
.share-editor__actions {
  display: flex;
  justify-content: flex-end;
  padding: 4px 0;
}
.share-editor__empty {
  color: var(--app-text-secondary);
}
</style>
