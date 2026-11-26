<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { createOrgProblem, getOrgProblem } from '@/api/orgs'
import { createProblem, getProblem, listActiveTags, updateProblem } from '@/api/problems'
import { getTeamProblem, updateTeamProblemStatement } from '@/api/teams'
import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { message } from '@/utils/feedback'
import type { ProblemCreatePayload, ProblemDetail, ProblemTagItem } from '@/types'
import CollapsibleEditor from '@/views/problems/components/CollapsibleEditor.vue'
import StatementMetaGrid from '@/views/problems/components/StatementMetaGrid.vue'
import WizardSteps from '@/views/problems/components/WizardSteps.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const isEdit = computed(() => Boolean(route.params.id ?? route.params.problemId))
/** 团队上下文（团队空间直建 / 团队题目编辑）：route 带 teamId */
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
const isTeam = computed(() => teamId.value !== null)
const orgId = computed(() => (route.params.orgId ? String(route.params.orgId) : null))
const isOrg = computed(() => orgId.value !== null)

const saving = ref(false)
const loading = ref(false)
const tagOptions = ref<ProblemTagItem[]>([])
const noteDefaultOpen = ref(false)

const form = reactive({
  title: '',
  background: '',
  description: '',
  input_description: '',
  output_description: '',
  note: '',
  solution: '',
  /** 标签名（激活标签；≤8） */
  tags: [] as string[],
  visibility: 'public',
  time_limit_ms: '1000',
  memory_limit_mb: '256',
  /** 难度分（手动填写；空 = 未评分） */
  difficulty: '',
})

const visibilityOptions = computed(() => {
  // 分支跟随：团队上下文，或当前可见性已是团队分支 → 团队分支选项；其余 → 全站分支
  const visibility = form.visibility
  if (isOrg.value) {
    return [{ label: t('problems.visibility.org_visible'), value: 'org_visible' }]
  }
  if (isTeam.value || visibility === 'team_visible' || visibility === 'admin_visible') {
    return [
      { label: t('teams.space.teamVisible'), value: 'team_visible' },
      { label: t('teams.space.adminVisible'), value: 'admin_visible' },
    ]
  }
  return [
    { label: t('problems.create.visibilityPublic'), value: 'public' },
    { label: t('problems.create.visibilityPrivate'), value: 'private' },
  ]
})

async function loadTagOptions(): Promise<void> {
  try {
    tagOptions.value = await listActiveTags()
  } catch {
    /* 标签加载失败不阻塞题面编辑 */
  }
}

async function loadExisting(): Promise<void> {
  if (!isEdit.value) return
  loading.value = true
  try {
    // 团队上下文回读走团队端点（快照题题库裸路径拦截）；保存也走团队端点
    const loaded: ProblemDetail = isOrg.value
      ? await getOrgProblem(orgId.value!, String(route.params.problemId))
      : isTeam.value
        ? await getTeamProblem(teamId.value!, String(route.params.id))
        : await getProblem(String(route.params.id))
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    Object.assign(form, {
      title: loaded.title,
      background: loaded.background,
      description: loaded.description,
      input_description: loaded.input_description ?? '',
      output_description: loaded.output_description ?? '',
      note: loaded.note ?? '',
      solution: loaded.solution ?? '',
      // loaded.tags 是 ProblemTagItem[]（含 id/name/color），form.tags 仅保存标签名
      tags: (loaded.tags ?? []).map((tag) => tag.name),
      visibility: loaded.visibility ?? 'public',
      time_limit_ms: String(loaded.time_limit_ms),
      memory_limit_mb: String(loaded.memory_limit_mb),
      difficulty:
        loaded.difficulty === null || loaded.difficulty === undefined
          ? ''
          : String(loaded.difficulty),
    })
    if (form.note) noteDefaultOpen.value = true
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    void router.push(
      isOrg.value
        ? `/orgs/${orgId.value}`
        : isTeam.value
          ? `/teams/${teamId.value}`
          : '/admin/problems',
    )
  } finally {
    loading.value = false
  }
}

function validate(): boolean {
  if (!form.title.trim() || !form.background.trim() || !form.description.trim()) {
    message.error(t('problems.wizard.needStatement'))
    return false
  }
  if (!form.input_description.trim() || !form.output_description.trim()) {
    message.error(t('problems.create.ioRequired'))
    return false
  }
  return true
}

function parseNumber(raw: string, fallback: number, min: number): number {
  const parsed = Number(raw)
  if (!Number.isFinite(parsed)) return fallback
  return Math.max(min, Math.trunc(parsed))
}

function buildPayload() {
  const difficulty = Number(form.difficulty)
  return {
    title: form.title,
    background: form.background,
    description: form.description,
    input_description: form.input_description || null,
    output_description: form.output_description || null,
    // 空字符串 = 清空说明（后端 PUT 语义："" 置 NULL）
    note: form.note,
    solution: form.solution || null,
    tags: form.tags,
    // 组织题 visibility 恒 org_visible，由服务端强制，不可显式提交
    visibility: isOrg.value ? undefined : form.visibility,
    time_limit_ms: parseNumber(form.time_limit_ms, 1000, 1),
    memory_limit_mb: parseNumber(form.memory_limit_mb, 256, 16),
    difficulty:
      form.difficulty.trim() === '' || !Number.isFinite(difficulty)
        ? null
        : Math.max(0, Math.trunc(difficulty)),
  }
}

/** 持久化题面（新建则先建草稿），成功返回题目 id，失败返回 null */
async function persist(): Promise<string | null> {
  if (!validate()) return null
  saving.value = true
  try {
    const payload = buildPayload()
    if (isEdit.value) {
      const id = String(route.params.id ?? route.params.problemId)
      if (isTeam.value) {
        // 团队上下文：ProblemUpdate extra=forbid，不可携带 team_id（归属由路径给定）
        await updateTeamProblemStatement(teamId.value!, id, payload)
      } else {
        await updateProblem(id, payload)
      }
      message.success(t('problems.create.saved'))
      return id
    }
    const created = isOrg.value
      ? await createOrgProblem(orgId.value!, payload as ProblemCreatePayload)
      : await createProblem({
          ...payload,
          // 团队上下文直建：仅创建载荷携带 team_id
          team_id: teamId.value ?? undefined,
        } as unknown as ProblemCreatePayload)
    message.success(t('problems.create.saved'))
    return created.id
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
    return null
  } finally {
    saving.value = false
  }
}

/** 下一步：持久化题面后进入「样例与测试点」页（团队上下文走团队路由） */
async function goNext(): Promise<void> {
  const id = await persist()
  if (!id) return
  const target = isOrg.value
    ? `/orgs/${orgId.value}/problems/${id}/edit/cases`
    : isTeam.value
      ? `/teams/${teamId.value}/problems/${id}/edit/cases`
      : `/admin/problems/${id}/edit/cases`
  // 新建用 replace：浏览器后退不会回到 /new 造成重复建草稿
  await (isEdit.value ? router.push(target) : router.replace(target))
}

/** 保存并退出：持久化题面后返回来源列表 */
async function saveAndExit(): Promise<void> {
  if (!(await persist())) return
  await router.push(
    isOrg.value
      ? `/orgs/${orgId.value}`
      : isTeam.value
        ? `/teams/${teamId.value}`
        : '/admin/problems',
  )
}

onMounted(() => {
  // 团队直建默认「全队成员可见」
  if (isTeam.value && !isEdit.value) form.visibility = 'team_visible'
  if (isOrg.value && !isEdit.value) form.visibility = 'org_visible'
  void loadTagOptions()
  void loadExisting()
})
</script>

<template>
  <div class="mx-auto w-full max-w-[1200px] px-4 pb-12 pt-4 sm:px-6">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div class="min-w-0">
        <h1 class="text-xl font-semibold leading-tight tracking-tight">
          {{ isEdit ? t('problems.create.editTitle') : t('problems.create.title') }}
        </h1>
        <div class="mt-2">
          <WizardSteps :current="1" />
        </div>
      </div>
    </header>

    <div class="my-5 h-px bg-border" role="separator" />

    <div v-if="loading" class="grid h-[320px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <form v-else class="space-y-8" @submit.prevent="goNext">
      <section>
        <h2 class="text-lg font-medium">{{ t('problems.create.sectionBasic') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('problems.create.sectionBasicHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />

        <div class="space-y-8">
          <div class="grid max-w-[520px] gap-2">
            <Label class="text-sm font-medium">
              {{ t('problems.create.name') }}
              <span class="text-destructive">*</span>
            </Label>
            <Input
              id="problem-title"
              v-model="form.title"
              class="h-10 text-sm"
              :aria-label="t('problems.create.name')"
            />
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('problems.create.titleHint') }}
            </p>
          </div>

          <StatementMetaGrid
            v-model:tags="form.tags"
            v-model:visibility="form.visibility"
            v-model:time-limit="form.time_limit_ms"
            v-model:memory-limit="form.memory_limit_mb"
            v-model:difficulty="form.difficulty"
            :visibility-options="visibilityOptions"
            :show-visibility="!isOrg"
            :tag-options="tagOptions"
          />
        </div>
      </section>

      <section>
        <div class="h-px bg-border" role="separator" />
        <h2 class="pt-8 text-lg font-medium">{{ t('problems.create.sectionStatement') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('problems.create.sectionStatementHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />

        <div class="space-y-8">
          <div class="grid gap-2">
            <Label class="text-sm font-medium">
              {{ t('problems.create.background') }}
              <span class="text-destructive">*</span>
            </Label>
            <MarkdownEditor v-model="form.background" min-height="180px" compact />
          </div>

          <div class="grid gap-2">
            <Label class="text-sm font-medium">
              {{ t('problems.create.statement') }}
              <span class="text-destructive">*</span>
            </Label>
            <MarkdownEditor v-model="form.description" min-height="360px" />
          </div>

          <div class="grid gap-6 lg:grid-cols-2">
            <div class="grid gap-2">
              <Label class="text-sm font-medium">
                {{ t('problems.create.inputDescription') }}
                <span class="text-destructive">*</span>
              </Label>
              <MarkdownEditor v-model="form.input_description" min-height="180px" compact />
            </div>
            <div class="grid gap-2">
              <Label class="text-sm font-medium">
                {{ t('problems.create.outputDescription') }}
                <span class="text-destructive">*</span>
              </Label>
              <MarkdownEditor v-model="form.output_description" min-height="180px" compact />
            </div>
          </div>

          <div class="space-y-3">
            <CollapsibleEditor
              v-model="form.note"
              :title="t('problems.create.note')"
              :add-label="t('problems.create.noteAdd')"
              :hide-label="t('problems.create.noteHide')"
              :default-open="noteDefaultOpen"
              min-height="160px"
              compact
            />
            <CollapsibleEditor
              v-model="form.solution"
              :title="t('problems.create.solution')"
              :add-label="t('problems.create.solutionAdd')"
              :hide-label="t('problems.create.solutionHide')"
              min-height="200px"
            />
          </div>
        </div>
      </section>

      <div class="flex flex-wrap justify-start gap-2 pt-2">
        <Button type="submit" :disabled="saving || loading">
          <Loader2 v-if="saving" class="size-4 animate-spin" />
          {{ t('problems.wizard.next') }}
        </Button>
        <Button type="button" variant="outline" :disabled="saving || loading" @click="saveAndExit">
          {{ t('problems.wizard.saveExit') }}
        </Button>
      </div>
    </form>
  </div>
</template>
