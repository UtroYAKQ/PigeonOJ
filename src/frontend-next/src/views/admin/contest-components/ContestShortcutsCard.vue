<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { LayoutList, ListChecks, Settings2 } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import ContestToolCard from './ContestToolCard.vue'

defineProps<{ canPreEdit: boolean }>()

defineEmits<{
  board: []
  submissions: []
  edit: []
}>()

const { t } = useI18n()
</script>

<template>
  <ContestToolCard :title="t('contests.tools.shortcuts')">
    <div class="flex flex-wrap gap-1.5">
      <Button variant="outline" size="sm" @click="$emit('board')">
        <LayoutList class="size-3.5" />
        {{ t('contests.tools.openBoard') }}
      </Button>
      <Button variant="outline" size="sm" @click="$emit('submissions')">
        <ListChecks class="size-3.5" />
        {{ t('contests.tools.openSubmissions') }}
      </Button>
      <Button variant="outline" size="sm" :disabled="!canPreEdit" @click="$emit('edit')">
        <Settings2 class="size-3.5" />
        {{ t('contests.tools.editContest') }}
      </Button>
    </div>
    <p v-if="!canPreEdit" class="text-[12px] text-muted-foreground">
      {{ t('contests.tools.editDisabled') }}
    </p>
  </ContestToolCard>
</template>
