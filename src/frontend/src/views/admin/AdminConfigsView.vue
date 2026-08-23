<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import * as adminApi from '@/api/admin'
import type { ConfigCategory, SystemConfigItem } from '@/api/types'
import { configCategories } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'

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
  'site.default_theme': [{ label: t('profile.light'), value: 'light' }, { label: t('profile.dark'), value: 'dark' }],
  'team.apply.review_rule': [{ label: t('config.manualReview'), value: 'manual' }, { label: t('config.autoApprove'), value: 'auto' }],
}))

const editorKind = computed<'boolean' | 'number' | 'select' | 'text' | 'switches'>(() => {
  if (typeof editValue.value === 'boolean') return 'boolean'
  if (typeof editValue.value === 'number') return 'number'
  if (editTarget.value && selectOptions.value[editTarget.value.config_key]) return 'select'
  if (editValue.value && typeof editValue.value === 'object' && !Array.isArray(editValue.value)) return 'switches'
  return 'text'
})

async function load() {
  loading.value = true
  try { items.value = await adminApi.adminListConfigs(activeCategory.value) }
  catch (e) { ElMessage.error(e instanceof Error ? e.message : t('config.loadFailed')) }
  finally { loading.value = false }
}
watch(activeCategory, load)
onMounted(load)

function openEdit(item: SystemConfigItem) {
  editTarget.value = item
  editValue.value = typeof item.config_value === 'object' && item.config_value !== null
    ? structuredClone(item.config_value) : item.config_value
  editDialog.value = true
}

function displayValue(value: unknown) {
  if (typeof value === 'boolean') return value ? t('config.booleanOn') : t('config.booleanOff')
  if (value && typeof value === 'object') return Object.entries(value as Record<string, unknown>).filter(([, enabled]) => enabled).map(([key]) => key).join(', ') || '—'
  return String(value ?? '—')
}

function switches(): Record<string, boolean> { return (editValue.value ?? {}) as Record<string, boolean> }

async function saveEdit() {
  if (!editTarget.value) return
  saving.value = true
  try {
    await adminApi.adminUpdateConfigs([{ id: editTarget.value.id, config_value: editValue.value }])
    ElMessage.success(t('config.saveSuccess'))
    editDialog.value = false
    await load()
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : t('config.saveFailed')) }
  finally { saving.value = false }
}
</script>

<template>
  <div class="configs-page">
    <header class="page-heading">
      <div><p class="page-heading__eyebrow">{{ t('nav.admin') }}</p><h1>{{ t('config.title') }}</h1><p>{{ t('config.descriptionText') }}</p></div>
    </header>
    <el-card shadow="never" class="configs-card">
    <el-tabs v-model="activeCategory" tab-position="left" class="configs__tabs">
      <el-tab-pane v-for="c in categories" :key="c.value" :name="c.value"><template #label>{{ c.label }}</template>
        <el-table v-loading="loading" :data="items" stripe>
          <el-table-column prop="config_key" :label="t('config.key')" width="260"><template #default="{ row }"><code>{{ row.config_key }}</code></template></el-table-column>
          <el-table-column :label="t('config.value')" min-width="220"><template #default="{ row }"><span>{{ displayValue(row.config_value) }}</span></template></el-table-column>
          <el-table-column prop="description" :label="t('config.description')" min-width="160" />
          <el-table-column prop="updated_by" :label="t('config.updater')" width="110" />
          <el-table-column :label="t('config.updatedAt')" width="150"><template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template></el-table-column>
          <el-table-column :label="t('action.edit')" width="90" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">{{ t('action.edit') }}</el-button></template></el-table-column>
          <template #empty><el-empty :description="t('config.empty')" :image-size="80" /></template>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="editDialog" :title="t('config.editTitle', { key: editTarget?.config_key ?? '' })" width="520px">
      <p class="configs__dialog-desc">{{ editTarget?.description }}</p>
      <el-switch v-if="editorKind === 'boolean'" v-model="editValue as boolean" :active-text="t('config.booleanOn')" :inactive-text="t('config.booleanOff')" />
      <el-input-number v-else-if="editorKind === 'number'" v-model="editValue as number" :min="0" class="configs__number" />
      <el-select v-else-if="editorKind === 'select'" v-model="editValue as string" class="configs__control"><el-option v-for="option in selectOptions[editTarget?.config_key ?? '']" :key="option.value" :label="option.label" :value="option.value" /></el-select>
      <div v-else-if="editorKind === 'switches'" class="configs__switches">
        <el-switch v-for="(_enabled, key) in switches()" :key="key" v-model="switches()[key]" :active-text="String(key)" />
      </div>
      <el-input v-else v-model="editValue as string" clearable class="configs__control" />
      <template #footer><el-button @click="editDialog = false">{{ t('action.cancel') }}</el-button><el-button type="primary" :loading="saving" @click="saveEdit">{{ t('action.save') }}</el-button></template>
    </el-dialog>
    </el-card>
  </div>
</template>

<style scoped>
.configs-page{display:grid;gap:20px}.page-heading{display:flex;align-items:end;justify-content:space-between}.page-heading__eyebrow{margin:0 0 6px;color:var(--el-color-primary);font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.page-heading h1{margin:0;font-size:26px;letter-spacing:-.035em}.page-heading p:not(.page-heading__eyebrow){max-width:650px;margin:8px 0 0;color:var(--app-text-muted);font-size:13px;line-height:1.6}.configs__tabs :deep(.el-tabs__header){margin-right:24px}.configs__tabs :deep(.el-tabs__item){height:42px;line-height:42px;font-weight:650}.configs__tabs :deep(.el-tabs__content){padding:0;min-width:0}.configs__dialog-desc{margin:0 0 14px;color:var(--app-text-muted);font-size:13px}.configs__control{width:100%}.configs__number{width:220px}.configs__switches{display:flex;flex-wrap:wrap;gap:12px 18px}@media(max-width:720px){.configs__tabs{display:block}.configs__tabs :deep(.el-tabs__header){margin:0 0 16px}.configs__tabs :deep(.el-tabs__nav-wrap){overflow:auto}.configs__tabs :deep(.el-tabs__nav-scroll){overflow:visible}}
</style>
