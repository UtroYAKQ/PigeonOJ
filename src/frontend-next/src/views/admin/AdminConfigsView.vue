<script setup lang="ts">
/**
 * 系统配置（/admin/configs）：按域（site / auth_email / team / contest / sandbox / log / community）
 * 读取并编辑 system_configs（docs/contracts/admin.md）。
 * 旧版为单文件 610 行（naive-ui 数据表 + 单弹窗）；现按分类导航 + 行式配置列表拆分，
 * 编辑器按配置键分流到 config-components/，站点域保存后触发热更新事件。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import * as adminApi from '@/api/admin'
import LineList from '@/components/common/LineList.vue'
import PageShell from '@/components/common/PageShell.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import { configCategories } from '@/constants/dict'
import { useAppStore } from '@/stores/app'
import { message } from '@/utils/feedback'
import type { ConfigCategory, SystemConfigItem } from '@/types'
import ConfigCategoryNav from './config-components/ConfigCategoryNav.vue'
import ConfigEditorDialog from './config-components/ConfigEditorDialog.vue'
import ConfigItemRow from './config-components/ConfigItemRow.vue'
import { isDeprecatedConfig } from './config-components/config-meta'

const { t } = useI18n()
const appStore = useAppStore()

const categories = computed(() =>
  configCategories().map((item) => ({ value: item.value as ConfigCategory, label: item.label })),
)
const activeCategory = ref<ConfigCategory>('site')
const items = ref<SystemConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)
const editorOpen = ref(false)
const editing = ref<SystemConfigItem | null>(null)

/** 分类切换竞态守卫：快速连点时只接受最后一次请求的结果 */
let loadSeq = 0

async function load(): Promise<void> {
  const seq = ++loadSeq
  loading.value = true
  try {
    const rows = await adminApi.adminListConfigs(activeCategory.value)
    if (seq !== loadSeq) return
    items.value = rows.filter((row) => !isDeprecatedConfig(row.config_key))
  } catch (error) {
    if (seq !== loadSeq) return
    items.value = []
    message.error(error instanceof Error ? error.message : t('config.loadFailed'))
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

function switchCategory(value: ConfigCategory): void {
  if (activeCategory.value === value) return
  activeCategory.value = value
  items.value = []
  void load()
}

function openEditor(item: SystemConfigItem): void {
  editing.value = item
  editorOpen.value = true
}

async function save(value: unknown): Promise<void> {
  if (!editing.value) return
  saving.value = true
  try {
    await adminApi.adminUpdateConfigs([{ id: editing.value.id, config_value: value }])
    message.success(t('config.saveSuccess'))
    editorOpen.value = false
    await load()
    // 站点域配置驱动壳层（站点名 / Logo / ICP / 默认主题）与首页，保存后热更新
    if (activeCategory.value === 'site') await appStore.loadSiteConfig()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('config.saveFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <PageShell :title="t('nav.configs')">
    <template #actions>
      <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
    </template>

    <div class="grid gap-8 lg:grid-cols-[208px_minmax(0,1fr)] lg:items-start">
      <ConfigCategoryNav
        :categories="categories"
        :model-value="activeCategory"
        @update:model-value="switchCategory"
      />

      <section>
        <h2 class="text-lg font-medium">{{ t('config.sectionTitle') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('config.sectionHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />

        <LineList
          :items="items"
          :loading="loading"
          :empty-text="t('config.empty')"
          :get-key="(item: SystemConfigItem) => item.id"
        >
          <template #skeleton>
            <div class="grid min-h-[260px] place-items-center">
              <Loader2 class="size-6 animate-spin text-muted-foreground" />
            </div>
          </template>
          <template #item="{ item }">
            <ConfigItemRow :item="item" @edit="openEditor(item)" />
          </template>
        </LineList>
      </section>
    </div>

    <ConfigEditorDialog v-model:open="editorOpen" :item="editing" :saving="saving" @save="save" />
  </PageShell>
</template>
