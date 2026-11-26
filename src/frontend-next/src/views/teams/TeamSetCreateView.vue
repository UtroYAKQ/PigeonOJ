<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, Plus, RefreshCw, Trash2 } from '@lucide/vue'

import {
  createTeamProblemSet,
  replaceTeamProblemSetItems,
  searchTeamArrangeableProblems,
} from '@/api/teams'
import ErrorState from '@/components/common/ErrorState.vue'
import LineList from '@/components/common/LineList.vue'
import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import ProblemPicker from '@/components/problemsets/ProblemPicker.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { message } from '@/utils/feedback'
import type { PageResult, ProblemSummary } from '@/types'
import { useTeamAdminGate } from './useTeamAdminGate'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const teamId = String(route.params.teamId)
const {
  allowed,
  loading: gateLoading,
  failed,
  forbidden,
  load: reloadGate,
} = useTeamAdminGate(teamId)

const submitting = ref(false)
const form = reactive({ title: '', description: '' })
const chosen = ref<ProblemSummary[]>([])
const pickerOpen = ref(false)
const chosenIds = computed(() => new Set(chosen.value.map((item) => item.id)))

function addProblem(problem: ProblemSummary): void {
  if (chosen.value.some((item) => item.id === problem.id)) return
  chosen.value.push(problem)
}

function removeProblem(index: number): void {
  chosen.value.splice(index, 1)
}

function pickerLoader(query: {
  page: number
  page_size: number
  keyword?: string
  mine?: boolean
}): Promise<PageResult<ProblemSummary>> {
  return searchTeamArrangeableProblems(teamId, {
    page: query.page,
    page_size: query.page_size,
    keyword: query.keyword,
  }) as Promise<PageResult<ProblemSummary>>
}

function backToTeam(): void {
  void router.replace(`/teams/${teamId}`)
}

async function retryGate(): Promise<void> {
  await reloadGate()
}

async function submitCreate(): Promise<void> {
  if (submitting.value) return
  if (!form.title.trim()) {
    message.warning(t('teams.space.setTitleRequired'))
    return
  }
  submitting.value = true
  try {
    const created = await createTeamProblemSet(teamId, {
      title: form.title.trim(),
      description: form.description.trim() || undefined,
    })
    if (chosen.value.length) {
      await replaceTeamProblemSetItems(teamId, created.id, {
        items: chosen.value.map((item, index) => ({
          problem_id: item.id,
          sort_order: index,
        })),
      })
    }
    message.success(t('teams.space.setCreated'))
    void router.replace(`/teams/${teamId}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <WorkbenchShell :title="t('teams.space.createSet')" :description="t('teams.space.setBasicHint')">
    <div v-if="gateLoading" class="grid min-h-0 flex-1 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div
      v-else-if="!allowed || failed"
      class="grid min-h-0 flex-1 place-items-center rounded-xl border border-border bg-card"
    >
      <ErrorState :message="forbidden ? t('teams.detail.forbidden') : t('teams.detail.loadFailed')">
        <template #actions>
          <Button v-if="failed" variant="outline" size="sm" @click="retryGate">
            <RefreshCw class="size-3.5" />
            {{ t('action.refresh') }}
          </Button>
          <Button variant="outline" size="sm" @click="backToTeam">
            {{ t('contests.list.backToTeam') }}
          </Button>
        </template>
      </ErrorState>
    </div>

    <form v-else class="min-h-0 flex-1 overflow-y-auto pb-6" @submit.prevent="submitCreate">
      <div class="mx-auto w-full max-w-[960px]">
        <h3 class="text-lg font-medium">{{ t('problemSets.form.basicTitle') }}</h3>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('teams.space.setBasicHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />

        <div class="space-y-8">
          <div class="grid gap-2">
            <div class="flex items-center justify-between">
              <Label for="team-set-title" class="text-sm font-medium">
                {{ t('problemSets.list.titleLabel') }}
                <span class="text-destructive">*</span>
              </Label>
              <span class="text-[11px] tabular-nums text-muted-foreground">
                {{ form.title.length }}/128
              </span>
            </div>
            <Input
              id="team-set-title"
              v-model="form.title"
              :maxlength="128"
              :placeholder="t('teams.space.setTitleRequired')"
              class="h-10 text-sm"
            />
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('teams.space.setTitleHint') }}
            </p>
          </div>

          <div class="grid gap-2">
            <div class="flex items-center justify-between gap-2">
              <Label class="text-sm font-medium">{{ t('problemSets.detail.problems') }}</Label>
              <Button type="button" variant="outline" @click="pickerOpen = true">
                <Plus class="size-4" />
                {{ t('problemSets.form.pickAdd') }}
              </Button>
            </div>
            <LineList
              :items="chosen"
              :empty-text="t('problemSets.detail.empty')"
              :get-key="(item: ProblemSummary) => item.id"
            >
              <template #item="{ item, index }">
                <div class="flex items-center gap-2 py-2">
                  <span class="min-w-0 flex-1 truncate text-sm">{{ item.title }}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    class="text-muted-foreground hover:text-destructive"
                    :aria-label="t('problemSets.detail.remove')"
                    @click="removeProblem(index)"
                  >
                    <Trash2 class="size-3.5" />
                  </Button>
                </div>
              </template>
            </LineList>
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('teams.space.setProblemsHint') }}
            </p>
          </div>
        </div>

        <div class="my-8 h-px bg-border" role="separator" />
        <h3 class="text-lg font-medium">{{ t('problemSets.list.descLabel') }}</h3>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('teams.space.setDescHint') }}
        </p>
        <div class="mt-5">
          <MarkdownEditor
            v-model="form.description"
            min-height="320px"
            :placeholder="t('problemSets.form.descPlaceholder')"
          />
        </div>

        <div class="mt-8 flex flex-wrap justify-start gap-2">
          <Button type="submit" :disabled="submitting || gateLoading">
            <Loader2 v-if="submitting" class="size-4 animate-spin" />
            {{ t('action.save') }}
          </Button>
          <Button type="button" variant="outline" :disabled="submitting" @click="backToTeam">
            {{ t('action.cancel') }}
          </Button>
        </div>
      </div>
    </form>

    <ProblemPicker
      v-model:show="pickerOpen"
      :chosen-ids="chosenIds"
      :loader="pickerLoader"
      @add="addProblem"
    />
  </WorkbenchShell>
</template>
