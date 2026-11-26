<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Loader2 } from '@lucide/vue'

import { getProblem } from '@/api/problems'
import ErrorState from '@/components/common/ErrorState.vue'
import PageShell from '@/components/common/PageShell.vue'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import { Button } from '@/components/ui/button'
import { goBackOrFallback } from '@/utils/navigation'
import { message } from '@/utils/feedback'
import type { ProblemDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const problem = ref<ProblemDetail | null>(null)
const loading = ref(false)

const problemId = computed(() => String(route.params.problemId ?? route.params.id))
const inSetContext = computed(() => Boolean(route.params.setId))

function backToManage(): void {
  if (inSetContext.value) {
    goBackOrFallback(router, `/admin/problem-sets/${String(route.params.setId)}`)
    return
  }
  goBackOrFallback(router, String(route.meta.backFallback ?? '/admin/problems'))
}

const backLabel = computed(() =>
  inSetContext.value
    ? t('problemSets.detail.backToSet')
    : route.meta.backLabelKey
      ? t(String(route.meta.backLabelKey))
      : t('problems.preview.backToList'),
)

async function load(): Promise<void> {
  loading.value = true
  try {
    problem.value = await getProblem(problemId.value)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <PageShell :title="t('problems.preview.title')" :description="t('problems.preview.description')">
    <template #actions>
      <Button variant="outline" size="sm" @click="backToManage">
        <ArrowLeft class="size-4" />
        {{ backLabel }}
      </Button>
    </template>

    <div v-if="loading" class="grid min-h-[320px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <section v-else-if="problem">
      <ProblemMetaBar :problem="problem" show-title show-reverify-tag />
      <div class="my-5 h-px bg-border" role="separator" />
      <ProblemStatement :problem="problem" />
    </section>

    <div v-else class="grid min-h-[320px] place-items-center">
      <ErrorState :message="t('problems.detail.loadFailed')" />
    </div>
  </PageShell>
</template>
