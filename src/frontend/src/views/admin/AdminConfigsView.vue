<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import * as adminApi from '@/api/admin'
import type { ConfigCategory, SystemConfigItem } from '@/types'
import { configCategories } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'
import { message } from '@/utils/feedback'

const { t } = useI18n()
const loading = ref(false)
const activeCategory = ref<ConfigCategory>('site')
const categories = computed(() => configCategories())
const items = ref<SystemConfigItem[]>([])
const editDialog = ref(false)
const editTarget = ref<SystemConfigItem | null>(null)
const editValue = ref<unknown>(null)
const saving = ref(false)

const selectOptions = computed<Record<string, Array<{ label: string; value: string }>>>(() => ({
  'site.default_theme': [
    { label: t('profile.light'), value: 'light' },
    { label: t('profile.dark'), value: 'dark' },
  ],
  'team.apply.review_rule': [
    { label: t('config.manualReview'), value: 'manual' },
    { label: t('config.autoApprove'), value: 'auto' },
  ],
}))

const editorKind = computed<'boolean' | 'number' | 'select' | 'text' | 'switches'>(() => {
  if (typeof editValue.value === 'boolean') return 'boolean'
  if (typeof editValue.value === 'number') return 'number'
  if (editTarget.value && selectOptions.value[editTarget.value.config_key]) return 'select'
  if (editValue.value && typeof editValue.value === 'object' && !Array.isArray(editValue.value))
    return 'switches'
  return 'text'
})

// 敏感配置（*.password，服务端掩码为 ******）用密码框编辑
const isSecretKey = computed(() => (editTarget.value?.config_key ?? '').endsWith('.password'))

async function load() {
  loading.value = true
  try {
    items.value = await adminApi.adminListConfigs(activeCategory.value)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('config.loadFailed'))
  } finally {
    loading.value = false
  }
}
watch(activeCategory, load)
onMounted(load)

function openEdit(item: SystemConfigItem) {
  editTarget.value = item
  editValue.value =
    typeof item.config_value === 'object' && item.config_value !== null
      ? structuredClone(item.config_value)
      : item.config_value
  editDialog.value = true
}

function displayValue(value: unknown) {
  if (typeof value === 'boolean') return value ? t('config.booleanOn') : t('config.booleanOff')
  if (value && typeof value === 'object')
    return (
      Object.entries(value as Record<string, unknown>)
        .filter(([, enabled]) => enabled)
        .map(([key]) => key)
        .join(', ') || '—'
    )
  return String(value ?? '—')
}

function switches(): Record<string, boolean> {
  return (editValue.value ?? {}) as Record<string, boolean>
}

async function saveEdit() {
  if (!editTarget.value) return
  saving.value = true
  try {
    await adminApi.adminUpdateConfigs([
      { id: editTarget.value.id, config_value: editValue.value },
    ])
    message.success(t('config.saveSuccess'))
    editDialog.value = false
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('config.saveFailed'))
  } finally {
    saving.value = false
  }
}

const columns = computed<DataTableColumns<SystemConfigItem>>(() => [
  {
    title: t('config.key'),
    key: 'config_key',
    width: 260,
    render: (row) => h('code', null, row.config_key),
  },
  {
    title: t('config.value'),
    key: 'value',
    minWidth: 220,
    render: (row) => displayValue(row.config_value),
  },
  { title: t('config.description'), key: 'description', minWidth: 160 },
  { title: t('config.updater'), key: 'updated_by', width: 110 },
  {
    title: t('config.updatedAt'),
    key: 'updated_at',
    width: 150,
    render: (row) => formatDateTime(row.updated_at),
  },
  {
    title: t('action.edit'),
    key: 'actions',
    width: 90,
    render: (row) =>
      h(
        NButton,
        { text: true, type: 'primary', onClick: () => openEdit(row) },
        { default: () => t('action.edit') },
      ),
  },
])
</script>

<template>
  <div class="page-stack">
    <n-card :bordered="false">
      <n-tabs v-model:value="activeCategory" type="line" animated>
        <n-tab-pane v-for="c in categories" :key="c.value" :name="c.value" :tab="c.label">
          <n-spin :show="loading">
            <n-data-table :columns="columns" :data="items" :bordered="false" />
            <n-empty
              v-if="!loading && !items.length"
              class="configs-empty"
              :description="t('config.empty')"
            />
          </n-spin>
        </n-tab-pane>
      </n-tabs>
    </n-card>

    <!-- 编辑配置 -->
    <n-modal
      v-model:show="editDialog"
      preset="card"
      style="width: min(520px, 92vw)"
      :title="t('config.editTitle', { key: editTarget?.config_key ?? '' })"
    >
      <p class="configs__desc">{{ editTarget?.description }}</p>
      <n-switch v-if="editorKind === 'boolean'" v-model:value="(editValue as boolean)" />
      <n-input-number
        v-else-if="editorKind === 'number'"
        v-model:value="(editValue as number)"
        :min="0"
        class="configs__number"
      />
      <n-select
        v-else-if="editorKind === 'select'"
        v-model:value="(editValue as string)"
        class="configs__control"
        :options="selectOptions[editTarget?.config_key ?? '']"
      />
      <div v-else-if="editorKind === 'switches'" class="configs__switches">
        <label v-for="(enabled, key) in switches()" :key="key" class="configs__switch">
          <span>{{ key }}</span>
          <n-switch v-model:value="switches()[key]" />
        </label>
      </div>
      <n-input
        v-else
        v-model:value="(editValue as string)"
        :type="isSecretKey ? 'password' : 'text'"
        :show-password-on="isSecretKey ? 'click' : undefined"
        clearable
        class="configs__control"
      />
      <template #footer>
        <div class="modal-footer">
          <n-button @click="editDialog = false">{{ t('action.cancel') }}</n-button>
          <n-button type="primary" :loading="saving" @click="saveEdit">{{
            t('action.save')
          }}</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.configs-empty {
  padding: 24px 0;
}
.configs__desc {
  margin: 0 0 14px;
  color: var(--app-text-secondary);
  font-size: 13px;
}
.configs__control,
.configs__number {
  width: 100%;
}
.configs__number {
  max-width: 220px;
}
.configs__switches {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
}
.configs__switch {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
