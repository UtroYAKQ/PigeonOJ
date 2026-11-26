<script setup lang="ts">
/**
 * 配置值编辑器（按配置键 / 值形态分流）：
 * 布尔开关、数字、枚举下拉、开关组对象、多行文本（邮箱模板带 iframe 预览）、密码、普通文本。
 * 海报列表与 Logo 上传由宿主单独渲染（需要上传能力）。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import PasswordField from '@/components/auth/PasswordField.vue'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import {
  buildEmailPreview,
  EMAIL_TEMPLATE_KEY,
  isSecretConfig,
  selectOptionsFor,
  type ConfigEditorKind,
} from './config-meta'

const props = defineProps<{
  kind: ConfigEditorKind
  configKey: string
  modelValue: unknown
}>()

const emit = defineEmits<{ 'update:modelValue': [value: unknown] }>()
const { t } = useI18n()

const text = computed({
  get: () => (typeof props.modelValue === 'string' ? props.modelValue : ''),
  set: (value: string) => emit('update:modelValue', value),
})

const numberText = computed(() =>
  typeof props.modelValue === 'number' ? String(props.modelValue) : '',
)

const booleanValue = computed(() => props.modelValue === true)

const options = computed(() => selectOptionsFor(props.configKey))

const switches = computed<Record<string, boolean>>(() =>
  props.modelValue && typeof props.modelValue === 'object' && !Array.isArray(props.modelValue)
    ? (props.modelValue as Record<string, boolean>)
    : {},
)

function toggleSwitch(key: string, checked: boolean): void {
  emit('update:modelValue', { ...switches.value, [key]: checked })
}

const multilineHint = computed(() =>
  props.configKey === EMAIL_TEMPLATE_KEY ? t('config.htmlTemplateHint') : '',
)

const previewHtml = computed(() =>
  props.configKey === EMAIL_TEMPLATE_KEY ? buildEmailPreview(text.value) : '',
)
</script>

<template>
  <div v-if="kind === 'boolean'" class="flex items-center gap-3 py-1">
    <Switch
      :model-value="booleanValue"
      @update:model-value="(value) => emit('update:modelValue', Boolean(value))"
    />
    <span class="text-sm text-muted-foreground">
      {{ booleanValue ? t('config.booleanOn') : t('config.booleanOff') }}
    </span>
  </div>

  <Input
    v-else-if="kind === 'number'"
    :model-value="numberText"
    type="number"
    min="0"
    class="h-10 max-w-[220px] text-sm tabular-nums"
    @update:model-value="emit('update:modelValue', $event === '' ? 0 : Number($event))"
  />

  <Select
    v-else-if="kind === 'select'"
    :model-value="text"
    @update:model-value="emit('update:modelValue', String($event))"
  >
    <SelectTrigger class="h-10 w-full max-w-[420px] text-sm">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </SelectItem>
    </SelectContent>
  </Select>

  <div v-else-if="kind === 'switches'" class="space-y-3">
    <div class="flex flex-wrap gap-x-6 gap-y-3">
      <label
        v-for="(enabled, key) in switches"
        :key="key"
        class="flex cursor-pointer items-center gap-2 text-sm"
      >
        <Switch
          :model-value="enabled"
          @update:model-value="(value) => toggleSwitch(String(key), Boolean(value))"
        />
        <span class="font-mono text-[13px]">{{ key }}</span>
      </label>
    </div>
    <p v-if="!Object.keys(switches).length" class="text-[13px] text-muted-foreground">
      {{ t('common.noData') }}
    </p>
  </div>

  <div
    v-else-if="kind === 'multiline'"
    class="grid gap-3"
    :class="previewHtml ? 'lg:grid-cols-2' : ''"
  >
    <div class="min-w-0">
      <Textarea
        v-model="text"
        class="min-h-[300px] font-mono text-[12.5px] leading-6"
        :placeholder="multilineHint"
      />
      <p v-if="multilineHint" class="mt-1.5 text-[13px] leading-5 text-muted-foreground">
        {{ multilineHint }}
      </p>
    </div>
    <div v-if="previewHtml" class="min-w-0">
      <p class="mb-1.5 text-[13px] font-medium text-muted-foreground">{{ t('config.preview') }}</p>
      <iframe
        :srcdoc="previewHtml"
        class="h-[300px] w-full rounded-lg border border-border bg-white"
        sandbox=""
        :title="t('config.preview')"
      />
    </div>
  </div>

  <PasswordField v-else-if="isSecretConfig(configKey)" v-model="text" autocomplete="new-password" />

  <Input v-else v-model="text" class="h-10 text-sm" />
</template>
