<script setup lang="ts">
/**
 * 团队比赛创建页（/teams/:teamId/contests/new）：团队空间直接创建
 * （contest_type='team'）；创建成功进入比赛编辑页编排题目。
 */
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from '@lucide/vue'

import { createTeamContest } from '@/api/teams'
import ErrorState from '@/components/common/ErrorState.vue'
import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { message } from '@/utils/feedback'
import type { ContestRuleType } from '@/types'
import DateTimeField from '@/components/common/DateTimeField.vue'
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
const form = reactive({
  title: '',
  description: '',
  rule_type: 'ACM' as ContestRuleType,
  start: null as number | null,
  end: null as number | null,
  regEnd: null as number | null,
})

function backToTeam(): void {
  void router.replace(`/teams/${teamId}`)
}

function onRuleTypeChange(value: unknown): void {
  form.rule_type = value === 'IOI' ? 'IOI' : 'ACM'
}

function validateTimes(): boolean {
  if (form.start == null || form.end == null || form.regEnd == null) {
    message.error(t('contests.wizard.needTimes'))
    return false
  }
  if (form.start >= form.end) {
    message.error(t('contests.wizard.timeRangeInvalid'))
    return false
  }
  if (form.regEnd > form.end) {
    message.error(t('contests.wizard.regEndAfterEnd'))
    return false
  }
  return true
}

async function submit(): Promise<void> {
  if (submitting.value) return
  if (!form.title.trim()) {
    message.warning(t('teams.space.contestTitleRequired'))
    return
  }
  if (!validateTimes()) return
  submitting.value = true
  try {
    const contest = await createTeamContest(teamId, {
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      rule_type: form.rule_type,
      start_time: new Date(form.start!).toISOString(),
      end_time: new Date(form.end!).toISOString(),
      register_start_time: new Date().toISOString(),
      register_end_time: new Date(form.regEnd!).toISOString(),
      problems: [],
    })
    message.success(t('teams.space.contestCreated'))
    await router.replace(`/teams/${teamId}/contests/${contest.id}/edit/problems`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <WorkbenchShell :title="t('teams.space.createContest')">
    <div v-if="gateLoading" class="grid min-h-0 flex-1 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div
      v-else-if="!allowed || failed"
      class="grid min-h-0 flex-1 place-items-center rounded-xl border border-border bg-card"
    >
      <ErrorState :message="forbidden ? t('teams.detail.forbidden') : t('teams.detail.loadFailed')">
        <template #actions>
          <Button v-if="failed" variant="outline" size="sm" @click="reloadGate">
            <RefreshCw class="size-3.5" />
            {{ t('action.refresh') }}
          </Button>
          <Button variant="outline" size="sm" @click="backToTeam">
            {{ t('contests.list.backToTeam') }}
          </Button>
        </template>
      </ErrorState>
    </div>

    <!-- 与设置页一致：分区标题 + 细分隔线 + 无边框表单 -->
    <form v-else class="min-h-0 flex-1 overflow-y-auto pb-6" @submit.prevent="submit">
      <div class="mx-auto w-full max-w-[960px]">
        <h3 class="text-lg font-medium">{{ t('contests.wizard.basic') }}</h3>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('teams.space.contestArrangeHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />

        <div class="space-y-8">
          <div class="grid gap-2">
            <div class="flex items-center justify-between">
              <Label for="team-contest-title" class="text-sm font-medium">
                {{ t('contests.list.titleLabel') }}
                <span class="text-destructive">*</span>
              </Label>
              <span class="text-[11px] tabular-nums text-muted-foreground">
                {{ form.title.length }}/128
              </span>
            </div>
            <Input
              id="team-contest-title"
              v-model="form.title"
              :maxlength="128"
              :placeholder="t('teams.space.contestTitleRequired')"
              class="h-10 text-sm"
            />
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('teams.space.contestTitleHint') }}
            </p>
          </div>

          <div class="grid gap-2">
            <Label class="text-sm font-medium">{{ t('contests.list.ruleType') }}</Label>
            <Tabs :model-value="form.rule_type" @update:model-value="onRuleTypeChange">
              <TabsList class="w-fit">
                <TabsTrigger value="ACM" class="px-4">ACM</TabsTrigger>
                <TabsTrigger value="IOI" class="px-4">IOI</TabsTrigger>
              </TabsList>
            </Tabs>
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('teams.space.contestRuleHint') }}
            </p>
          </div>

          <div class="grid gap-2">
            <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <div class="grid gap-2">
                <Label for="team-contest-start" class="text-sm font-medium">
                  {{ t('contests.list.startTime') }}
                  <span class="text-destructive">*</span>
                </Label>
                <DateTimeField id="team-contest-start" v-model="form.start" />
              </div>
              <div class="grid gap-2">
                <Label for="team-contest-end" class="text-sm font-medium">
                  {{ t('contests.list.endTime') }}
                  <span class="text-destructive">*</span>
                </Label>
                <DateTimeField id="team-contest-end" v-model="form.end" />
              </div>
              <div class="grid gap-2 sm:col-span-2 xl:col-span-1">
                <Label for="team-contest-reg-end" class="text-sm font-medium">
                  {{ t('contests.list.regEndTime') }}
                  <span class="text-destructive">*</span>
                </Label>
                <DateTimeField id="team-contest-reg-end" v-model="form.regEnd" />
              </div>
            </div>
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('teams.space.contestTimeHint') }}
            </p>
          </div>
        </div>

        <div class="my-8 h-px bg-border" role="separator" />
        <h3 class="text-lg font-medium">{{ t('contests.detail.about') }}</h3>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('contests.list.descLabel') }}
        </p>
        <div class="mt-5">
          <MarkdownEditor
            v-model="form.description"
            min-height="320px"
            :placeholder="t('contests.list.descLabel')"
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
  </WorkbenchShell>
</template>
