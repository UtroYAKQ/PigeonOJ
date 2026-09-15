<script setup lang="ts">
/**
 * 团队比赛创建页（/teams/:teamId/contests/new）：团队空间直接创建
 * （contest_type='team'，team_creator / team_admin，docs/contracts/teams.md 团队空间节）。
 * 精简表单：标题 / 赛制 / 起止时间 / 报名截止；创建成功 → replace 回团队详情，
 * 编排题目在比赛编辑页进行（与后台向导一致）。
 */
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { createTeamContest } from '@/api/teams'
import { message } from '@/utils/feedback'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const teamId = String(route.params.teamId)
const submitting = ref(false)

const form = reactive({
  title: '',
  description: '',
  rule_type: 'ACM' as 'ACM' | 'IOI',
  start: null as number | null,
  end: null as number | null,
  regEnd: null as number | null,
})

function backToTeam() {
  void router.replace(`/teams/${teamId}`)
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

async function submit() {
  if (!form.title.trim()) {
    message.warning(t('teams.space.contestTitleRequired'))
    return
  }
  if (!validateTimes()) return
  submitting.value = true
  try {
    const created = await createTeamContest(teamId, {
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
    await router.replace(`/teams/${teamId}/contests/${created.id}/edit/problems`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <WorkbenchShell :title="t('teams.space.createContest')">
    <template #header-extra>
      <n-button size="small" @click="backToTeam">{{ t('action.cancel') }}</n-button>
    </template>

    <n-form label-placement="top" class="create-form" @submit.prevent>
      <n-form-item :label="t('contests.list.titleLabel')" required>
        <n-input
          v-model:value="form.title"
          size="large"
          :maxlength="128"
          show-count
          :placeholder="t('teams.space.contestTitleRequired')"
        />
      </n-form-item>
      <div class="meta-row">
        <n-form-item :label="t('contests.list.ruleType')">
          <n-radio-group v-model:value="form.rule_type">
            <n-radio-button value="ACM">ACM</n-radio-button>
            <n-radio-button value="IOI">IOI</n-radio-button>
          </n-radio-group>
        </n-form-item>
        <n-form-item :label="t('contests.list.startTime')">
          <n-date-picker v-model:value="form.start" type="datetime" style="width: 100%" />
        </n-form-item>
        <n-form-item :label="t('contests.list.endTime')">
          <n-date-picker v-model:value="form.end" type="datetime" style="width: 100%" />
        </n-form-item>
        <n-form-item :label="t('contests.list.regEndTime')">
          <n-date-picker v-model:value="form.regEnd" type="datetime" style="width: 100%" />
        </n-form-item>
      </div>
      <n-form-item :label="t('contests.list.descLabel')" :show-feedback="false">
        <MarkdownEditor
          v-model="form.description"
          min-height="240px"
          :placeholder="t('contests.list.descLabel')"
        />
      </n-form-item>
      <div class="form-actions">
        <n-button :disabled="submitting" @click="backToTeam">{{ t('action.cancel') }}</n-button>
        <n-button type="primary" :loading="submitting" @click="submit">
          {{ t('action.save') }}
        </n-button>
      </div>
    </n-form>
  </WorkbenchShell>
</template>

<style scoped>
.create-form {
  max-width: 860px;
}
.meta-row {
  display: grid;
  grid-template-columns: auto repeat(3, minmax(0, 1fr));
  gap: 0 16px;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
@media (max-width: 900px) {
  .meta-row {
    grid-template-columns: 1fr;
  }
}
</style>
