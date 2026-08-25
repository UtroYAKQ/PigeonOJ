<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { adminArchiveTag, adminCreateTag, adminListTags, adminUpdateTag } from '@/api/admin'
import type { ProblemTagItem } from '@/types'
import { formatDateTime } from '@/utils/format'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import ModalFooter from '@/components/ModalFooter.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'

const { t } = useI18n()
const loading = ref(false)
const list = ref<ProblemTagItem[]>([])

const editorDialog = ref(false)
const editing = ref<ProblemTagItem | null>(null)
/** editing=null 表示新建；name/color 为表单字段 */
const formName = ref('')
const formColor = ref<string | null>(null)
const submitting = ref(false)

async function load() {
  loading.value = true
  try {
    list.value = await adminListTags()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openCreate() {
  editing.value = null
  formName.value = ''
  formColor.value = null
  editorDialog.value = true
}
function openEdit(tag: ProblemTagItem) {
  editing.value = tag
  formName.value = tag.name
  formColor.value = tag.color ?? null
  editorDialog.value = true
}
function cancelEditor() {
  editorDialog.value = false
}
async function submitEditor() {
  const name = formName.value.trim()
  if (!name) return
  submitting.value = true
  try {
    if (editing.value) {
      await adminUpdateTag(editing.value.id, { name, color: formColor.value || null })
      message.success(t('admin.tags.updated'))
    } else {
      await adminCreateTag({ name, color: formColor.value || null })
      message.success(t('admin.tags.created'))
    }
    editorDialog.value = false
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}

function doArchive(tag: ProblemTagItem) {
  confirmAsyncDialog({
    title: t('admin.tags.archive'),
    content: t('admin.tags.archiveConfirm', { name: tag.name }),
    positiveText: t('admin.tags.archive'),
    action: () => adminArchiveTag(tag.id),
    successMessage: t('admin.tags.archivedSuccess'),
    onAfterSuccess: () => load(),
  })
}

const columns = computed<DataTableColumns<ProblemTagItem>>(() => [
  {
    title: t('admin.tags.name'),
    key: 'name',
    minWidth: 180,
    render(row) {
      return h(
        NTag,
        row.color
          ? {
              size: 'small',
              color: { color: row.color, textColor: '#fff', borderColor: row.color },
            }
          : { size: 'small' },
        { default: () => row.name },
      )
    },
  },
  {
    title: t('admin.tags.color'),
    key: 'color',
    width: 100,
    render(row) {
      if (!row.color) return h('span', { class: 'cell-muted' }, '—')
      return h('div', { class: 'color-cell' }, [
        h('span', { class: 'color-dot', style: { background: row.color } }),
        h('span', { class: 'cell-muted' }, row.color),
      ])
    },
  },
  {
    title: t('admin.tags.status'),
    key: 'status',
    width: 100,
    render(row) {
      return h(
        NTag,
        { size: 'small', type: row.status === 'archived' ? 'default' : 'success', bordered: false },
        { default: () => t(row.status === 'archived' ? 'admin.tags.archived' : 'admin.tags.active') },
      )
    },
  },
  {
    title: t('admin.tags.createdAt'),
    key: 'created_at',
    width: 160,
    render: (row) => formatDateTime(row.created_at ?? ''),
  },
  {
    title: t('action.edit'),
    key: 'actions',
    width: 150,
    fixed: 'right',
    render(row) {
      const buttons = [
        h(
          NButton,
          { text: true, type: 'primary', onClick: () => openEdit(row) },
          { default: () => t('action.edit') },
        ),
      ]
      if (row.status !== 'archived') {
        buttons.push(
          h(
            NButton,
            { text: true, type: 'error', onClick: () => doArchive(row) },
            { default: () => t('admin.tags.archive') },
          ),
        )
      }
      return h('div', { class: 'cell-actions' }, buttons)
    },
  },
])
</script>

<template>
  <div class="page-fill">
    <n-card :title="t('admin.tags.title')" :bordered="false">
      <SearchFilterBar :show-search="false">
        <template #actions>
          <n-button type="primary" size="small" @click="openCreate">
            {{ t('admin.tags.create') }}
          </n-button>
        </template>
      </SearchFilterBar>

      <n-data-table
        v-if="loading || list.length"
        class="table-fill"
        :columns="columns"
        :data="list"
        :loading="loading"
        :bordered="false"
      />
      <div v-else class="table-fill-empty">
        <n-empty size="large" :description="t('admin.tags.empty')" />
      </div>

      <!-- 新建 / 编辑标签 -->
      <n-modal
        v-model:show="editorDialog"
        preset="card"
        style="width: min(420px, 92vw)"
        :title="editing ? t('admin.tags.edit') : t('admin.tags.create')"
      >
        <n-form label-placement="top">
          <n-form-item :label="t('admin.tags.name')">
            <n-input
              v-model:value="formName"
              maxlength="32"
              show-count
              :placeholder="t('admin.tags.namePlaceholder')"
              @keyup.enter="submitEditor"
            />
          </n-form-item>
          <n-form-item :label="t('admin.tags.color')">
            <n-color-picker v-model:value="formColor" :show-alpha="false" :modes="['hex']" />
          </n-form-item>
        </n-form>
        <template #footer>
          <ModalFooter :loading="submitting" @cancel="cancelEditor" @confirm="submitEditor" />
        </template>
      </n-modal>
    </n-card>
  </div>
</template>

<style scoped>
.color-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.color-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
}
.cell-muted {
  color: var(--app-text-secondary);
  font-size: 12px;
}
</style>
