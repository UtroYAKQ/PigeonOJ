<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, Languages } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { setLocale } from '@/i18n'

const { locale, t } = useI18n()

const label = computed(() => (locale.value === 'zh-CN' ? t('app.localeZh') : 'EN'))

function choose(value: 'zh-CN' | 'en-US'): void {
  setLocale(value)
}
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button variant="ghost" size="sm" class="gap-1.5 px-2" :aria-label="t('app.language')">
        <Languages class="size-4 text-muted-foreground" />
        <span class="text-[13px]">{{ label }}</span>
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end" class="w-36">
      <DropdownMenuItem class="cursor-pointer" @select="choose('zh-CN')">
        <Check v-if="locale === 'zh-CN'" class="size-4" />
        <span v-else class="size-4" />
        {{ t('app.localeZh') }}
      </DropdownMenuItem>
      <DropdownMenuItem class="cursor-pointer" @select="choose('en-US')">
        <Check v-if="locale === 'en-US'" class="size-4" />
        <span v-else class="size-4" />
        {{ t('app.localeEn') }}
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
