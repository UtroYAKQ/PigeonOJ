<script setup lang="ts">
/**
 * 系统配置编辑弹窗：按配置键选择编辑器（海报列表 / Logo 上传 / 动态值编辑器），
 * 保存动作交由宿主执行（宿主负责调用 PUT /admin/configs 与站点配置热更新）。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { SystemConfigItem } from '@/types'
import BannerListEditor from './BannerListEditor.vue'
import ConfigValueEditor from './ConfigValueEditor.vue'
import LogoField from './LogoField.vue'
import { toBannerDraft, normalizeBanners, type BannerDraft } from './banners'
import { BANNERS_KEY, EMAIL_TEMPLATE_KEY, resolveEditorKind } from './config-meta'

const props = defineProps<{
  open: boolean
  item: SystemConfigItem | null
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  save: [value: unknown]
}>()

const { t } = useI18n()

const value = ref<unknown>(null)
const banners = ref<BannerDraft[]>([])

const kind = computed(() => resolveEditorKind(props.item, value.value))

const dialogClass = computed(() => {
  if (kind.value === 'banners') return 'sm:max-w-[900px]'
  if (kind.value === 'image') return 'sm:max-w-[620px]'
  if (kind.value === 'multiline' && props.item?.config_key === EMAIL_TEMPLATE_KEY) {
    return 'sm:max-w-[920px]'
  }
  return 'sm:max-w-[520px]'
})

const textValue = computed({
  get: () => (typeof value.value === 'string' ? value.value : ''),
  set: (next: string) => {
    value.value = next
  },
})

watch(
  () => [props.open, props.item] as const,
  ([open]) => {
    if (!open || !props.item) return
    const raw = props.item.config_value
    // 对象 / 数组用结构化克隆，编辑期间的草稿不污染列表缓存
    value.value = typeof raw === 'object' && raw !== null ? structuredClone(raw) : raw
    banners.value = props.item.config_key === BANNERS_KEY ? toBannerDraft(raw) : []
  },
  { immediate: true },
)

function submit(): void {
  if (!props.item) return
  if (props.item.config_key === BANNERS_KEY) {
    // 无图片的半成品条目丢弃
    emit('save', normalizeBanners(banners.value))
    return
  }
  emit('save', value.value)
}

function close(): void {
  emit('update:open', false)
}
</script>

<template>
  <Dialog :open="open" @update:open="(next) => emit('update:open', next)">
    <DialogContent :class="[dialogClass, 'max-h-[86vh] overflow-y-auto']">
      <DialogHeader>
        <DialogTitle class="pr-8 text-lg font-medium">
          {{ t('config.editTitle', { key: item?.config_key ?? '' }) }}
        </DialogTitle>
        <DialogDescription v-if="item?.description" class="text-sm leading-5">
          {{ item.description }}
        </DialogDescription>
        <DialogDescription v-else class="sr-only">
          {{ t('config.editTitle', { key: item?.config_key ?? '' }) }}
        </DialogDescription>
      </DialogHeader>

      <div v-if="item" class="min-w-0">
        <template v-if="kind === 'banners'">
          <BannerListEditor v-model="banners" />
        </template>
        <LogoField v-else-if="kind === 'image'" v-model="textValue" />
        <ConfigValueEditor v-else v-model="value" :kind="kind" :config-key="item.config_key" />
      </div>

      <DialogFooter class="gap-2">
        <Button variant="outline" size="sm" :disabled="saving" @click="close">
          {{ t('action.cancel') }}
        </Button>
        <Button size="sm" :disabled="saving || !item" @click="submit">
          <Loader2 v-if="saving" class="size-3.5 animate-spin" />
          {{ t('action.save') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
