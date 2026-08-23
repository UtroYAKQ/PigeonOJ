<script setup lang="ts">
import { MoreFilled } from '@element-plus/icons-vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createSubmission, listSubmissions } from '@/api/judge'
import { archiveProblem, getProblem, publishProblem } from '@/api/problems'
import CodeEditor from '@/components/CodeEditor.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import type { ProblemDetailEx, ProblemDifficulty, ProblemLanguage, Submission } from '@/types'

const route = useRoute(); const router = useRouter(); const { t } = useI18n()
const problem = ref<ProblemDetailEx | null>(null)
const loading = ref(false); const submitting = ref(false)
const publishing = ref(false); const archiving = ref(false)
const language = ref<ProblemLanguage>('cpp17')
const mySubmissions = ref<Submission[]>([])
const subsVisible = ref(false)

const code = ref('')

const statusTagType = computed(() => {
  const s = problem.value?.status
  return s === 'published' ? 'success' : s === 'archived' ? 'info' : 'warning'
})
function difficultyTagType(difficulty: ProblemDifficulty): 'success' | 'warning' | 'danger' {
  return difficulty === 'hard' ? 'danger' : difficulty === 'medium' ? 'warning' : 'success'
}
const statusLabelKey: Record<string, string> = {
  draft: 'problems.list.statusDraft',
  published: 'problems.list.statusPublished',
  archived: 'problems.list.statusArchived',
}

async function copyText(text: string) {
  try { await navigator.clipboard.writeText(text); ElMessage.success(t('problems.detail.copied')) } catch { ElMessage.error(t('common.operationFailed')) }
}

async function load() {
  loading.value = true
  try {
    problem.value = await getProblem(String(route.params.id))
    await loadMySubmissions()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  } finally { loading.value = false }
}
async function loadMySubmissions() {
  try {
    const result = await listSubmissions({ problem_id: String(route.params.id), page_size: 5 })
    mySubmissions.value = result.items
  } catch { /* 未登录等场景静默 */ }
}

function openSubmission(row: Submission) {
  subsVisible.value = false
  router.push(`/problems/${route.params.id}/submissions/${row.id}`)
}

/** 卡片头三点菜单：编辑 / 发布 / 归档 */
function onManage(command: string) {
  if (!problem.value) return
  if (command === 'edit') router.push(`/problems/${problem.value.id}/edit`)
  else if (command === 'publish') doPublish()
  else if (command === 'archive') doArchive()
}

async function submit() {
  if (!problem.value || submitting.value) return
  // 提交前二次确认，避免误触
  try {
    await ElMessageBox.confirm(t('problems.detail.submitConfirm'), t('problems.detail.submit'), {
      type: 'info',
      confirmButtonText: t('problems.detail.submit'),
      cancelButtonText: t('action.cancel'),
    })
  } catch { return }
  submitting.value = true
  try {
    const result = await createSubmission({ problem_id: problem.value.id, language: language.value, code: code.value })
    router.push(`/problems/${problem.value.id}/submissions/${result.submission_id}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.detail.submitFailed'))
  } finally { submitting.value = false }
}

async function doPublish() {
  if (!problem.value) return
  publishing.value = true
  try {
    const updated = await publishProblem(problem.value.id)
    problem.value = { ...problem.value, ...updated }
    ElMessage.success(t('problems.detail.publishSuccess'))
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : t('common.operationFailed')) } finally { publishing.value = false }
}
async function doArchive() {
  if (!problem.value) return
  archiving.value = true
  try {
    const updated = await archiveProblem(problem.value.id)
    problem.value = { ...problem.value, ...updated }
    ElMessage.success(t('problems.detail.archiveSuccess'))
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : t('common.operationFailed')) } finally { archiving.value = false }
}

onMounted(load)

// ---- 可拖拽分栏：桌面端左右独立滚动，比例持久化；窄屏自动上下堆叠 ----
const SPLIT_KEY = 'pigeonoj.problems.splitRatio'
const desktopQuery = window.matchMedia('(min-width: 900px)')
const isDesktop = ref(desktopQuery.matches)
const splitRef = ref<HTMLElement>()
const ratio = ref(loadRatio())
const splitHeight = ref('')

function loadRatio(): number {
  const raw = Number(localStorage.getItem(SPLIT_KEY))
  return Number.isFinite(raw) && raw >= 0.25 && raw <= 0.75 ? raw : 0.5
}
let resizing = false
function startResize(event: PointerEvent) {
  if (!isDesktop.value) return
  event.preventDefault()
  resizing = true
  document.body.classList.add('is-splitting')
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', endResize)
}
function onPointerMove(event: PointerEvent) {
  if (!resizing || !splitRef.value) return
  const rect = splitRef.value.getBoundingClientRect()
  ratio.value = Math.min(0.75, Math.max(0.25, (event.clientX - rect.left) / rect.width))
}
function endResize() {
  if (!resizing) return
  resizing = false
  document.body.classList.remove('is-splitting')
  localStorage.setItem(SPLIT_KEY, String(ratio.value))
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', endResize)
}
function resetSplit() {
  ratio.value = 0.5
  localStorage.setItem(SPLIT_KEY, String(ratio.value))
}

/** 计算分栏可用高度：视口高度 - 分栏上方内容 - 滚动容器上下内边距，使两栏独立滚动而非整页滚动 */
function updateSplitHeight() {
  if (!isDesktop.value) { splitHeight.value = ''; return }
  const el = splitRef.value
  const scroller = el?.closest('.app-main') as HTMLElement | null
  if (!el || !scroller) { splitHeight.value = ''; return }
  const styles = getComputedStyle(scroller)
  const padTop = parseFloat(styles.paddingTop) || 0
  const padBottom = parseFloat(styles.paddingBottom) || 0
  // 分栏顶部相对滚动容器内容区顶部的距离（含已滚动量）
  const topGap = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - padTop
  // 可用高度 = 内容区总高(clientHeight 已含上下 padding) - 上 padding - 下 padding - 顶部距离；取整并留 1px 余量防亚像素溢出
  const height = Math.max(420, Math.floor(scroller.clientHeight - padTop - padBottom - topGap) - 1)
  splitHeight.value = `${height}px`
}
const layoutStyle = computed(() =>
  isDesktop.value
    ? ({ '--split': `${ratio.value * 100}%`, height: splitHeight.value || undefined } as Record<string, string | undefined>)
    : {},
)
function onDesktopChange(event: MediaQueryListEvent) {
  isDesktop.value = event.matches
  updateSplitHeight()
}
watch(problem, () => nextTick(updateSplitHeight))

onMounted(() => {
  desktopQuery.addEventListener('change', onDesktopChange)
  window.addEventListener('resize', updateSplitHeight)
  window.addEventListener('pigeonoj:locale-change', updateSplitHeight)
})
onBeforeUnmount(() => {
  desktopQuery.removeEventListener('change', onDesktopChange)
  window.removeEventListener('resize', updateSplitHeight)
  window.removeEventListener('pigeonoj:locale-change', updateSplitHeight)
  document.body.classList.remove('is-splitting')
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', endResize)
})
</script>

<template>
  <div v-loading="loading" class="problem-detail">
    <div v-if="problem" ref="splitRef" class="problem-detail__layout" :class="{ stacked: !isDesktop }" :style="layoutStyle">
      <!-- 左栏：题面（独立滚动） -->
      <section class="problem-detail__statement">
        <el-card shadow="never" class="statement-card">
          <template #header>
            <div class="statement-card__head">
              <div class="statement-card__heading">
                <h2 class="statement-card__title">{{ problem.title }}</h2>
                <div class="problem-detail__meta">
                  <el-tag size="small" :type="difficultyTagType(problem.difficulty)" effect="light">{{ t(`problems.difficulty.${problem.difficulty}`) }}</el-tag>
                  <span>{{ problem.time_limit_ms }} ms</span>
                  <span>{{ problem.memory_limit_mb }} MB</span>
                  <el-tag size="small">{{ problem.spj ? 'SPJ' : t('problems.detail.standard') }}</el-tag>
                  <el-tag v-if="problem.status !== 'published'" size="small" :type="statusTagType">{{ t(statusLabelKey[problem.status] ?? problem.status) }}</el-tag>
                  <el-tag v-if="problem.visibility !== 'public'" size="small" type="info" effect="plain">{{ t(`problems.visibility.${problem.visibility}`) }}</el-tag>
                  <el-tag v-for="tag in problem.tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
                </div>
              </div>
              <el-dropdown v-if="problem.can_manage && problem.status !== 'archived'" trigger="click" @command="onManage">
                <el-button :icon="MoreFilled" text circle aria-haspopup="menu"/>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">{{ t('action.edit') }}</el-dropdown-item>
                    <el-dropdown-item v-if="problem.status === 'draft'" divided command="publish">{{ t('problems.detail.publish') }}</el-dropdown-item>
                    <el-dropdown-item command="archive">{{ t('problems.detail.archive') }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>

          <MarkdownView :source="problem.description" />

          <template v-if="problem.input_description">
            <h3 class="statement-card__subtitle">{{ t('problems.detail.inputDescription') }}</h3>
            <MarkdownView :source="problem.input_description" />
          </template>
          <template v-if="problem.output_description">
            <h3 class="statement-card__subtitle">{{ t('problems.detail.outputDescription') }}</h3>
            <MarkdownView :source="problem.output_description" />
          </template>

          <h3 class="statement-card__subtitle">{{ t('problems.detail.samples') }}</h3>
          <div v-if="problem.samples.length" class="samples">
            <div v-for="(sample, index) in problem.samples" :key="sample.id ?? index" class="sample-block">
              <div class="sample-block__head">
                <strong>#{{ index + 1 }} {{ sample.name }}</strong>
                <el-button link size="small" @click="copyText(sample.input)">{{ t('problems.detail.copyInput') }}</el-button>
              </div>
              <div class="sample-grid2">
                <div><p class="sample-label">{{ t('problems.detail.stdin') }}</p><pre class="result-box sample-io">{{ sample.input || t('problems.detail.noOutput') }}</pre></div>
                <div><p class="sample-label">{{ t('problems.submission.expectedOutput') }}</p><pre class="result-box sample-io">{{ sample.output || t('problems.detail.noOutput') }}</pre></div>
              </div>
            </div>
            <p class="form-hint">{{ t('problems.detail.sampleHint') }}</p>
          </div>
          <el-empty v-else :description="t('problems.detail.noSamples')" :image-size="60"/>

          <template v-if="problem.solution">
            <h3 class="statement-card__subtitle">{{ t('problems.detail.solution') }}</h3>
            <MarkdownView :source="problem.solution" />
          </template>
        </el-card>
      </section>

      <!-- 可拖拽分隔条 -->
      <div
        class="problem-detail__divider"
        role="separator"
        aria-orientation="vertical"
        :aria-label="t('problems.detail.resizeHint')"
        :title="t('problems.detail.resizeHint')"
        @pointerdown="startResize"
        @dblclick="resetSplit"
      />

      <!-- 右栏：编辑器（提交历史收进工具栏按钮） -->
      <section class="problem-detail__workbench">
        <div class="editor-shell">
          <div class="editor-toolbar">
            <el-select v-model="language" class="editor-toolbar__language">
              <el-option label="C++17" value="cpp17"/>
              <el-option label="Python 3.12" value="python3.12"/>
              <el-option label="Java 21" value="java21"/>
            </el-select>
            <div class="editor-toolbar__actions">
              <el-button @click="subsVisible = true">{{ t('problems.detail.mySubmissions') }}</el-button>
              <el-button type="primary" :loading="submitting" @click="submit">{{ t('problems.detail.submit') }}</el-button>
            </div>
          </div>
          <div class="editor-wrap">
            <CodeEditor v-model="code" :language="language"/>
          </div>
        </div>
      </section>
    </div>

    <!-- 提交历史弹窗 -->
    <el-dialog v-model="subsVisible" :title="t('problems.detail.mySubmissions')" width="min(720px, 92vw)" append-to-body>
      <el-table v-if="mySubmissions.length" :data="mySubmissions" size="small" class="sub-table"
        @row-click="openSubmission">
        <el-table-column prop="status" :label="t('problems.detail.status')" min-width="150">
          <template #default="{ row }"><el-tag size="small" :type="row.status === 'accepted' ? 'success' : ['pending', 'judging'].includes(row.status) ? 'info' : 'danger'">{{ t(`problems.status.${row.status}`) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="score" :label="t('problems.submission.score')" width="80"/>
        <el-table-column :label="t('problems.submission.time')" width="110">
          <template #default="{ row }">{{ row.time_used_ms ?? '-' }} ms</template>
        </el-table-column>
        <el-table-column prop="language" :label="t('problems.detail.language')" width="120"/>
      </el-table>
      <el-empty v-else :description="t('problems.detail.noSubmissions')" :image-size="60"/>
    </el-dialog>
  </div>
</template>

<style scoped>
.problem-detail__layout {
  display: grid;
  grid-template-columns: minmax(300px, var(--split, 50%)) auto minmax(360px, 1fr);
  align-items: stretch;
  gap: 4px;
  min-height: 420px;
}
.problem-detail__statement { display: flex; flex-direction: column; overflow-y: auto; min-height: 0; padding-right: 6px; }
.statement-card { flex: 1; }

.statement-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; width: 100%; }
.statement-card__heading { min-width: 0; }
.statement-card__title { margin: 0; font-size: 17px; line-height: 1.35; letter-spacing: -.02em; }
.problem-detail__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; color: var(--app-text-muted); font-size: 12px; }
.statement-card__subtitle { margin: 22px 0 8px; padding-top: 16px; border-top: 1px solid var(--app-border); font-size: 15px; letter-spacing: -.01em; }

.samples { display: grid; gap: 14px; }
.sample-block { border: 1px solid var(--app-border); border-radius: 11px; padding: 12px; background: var(--app-surface-muted); }
.sample-block__head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.sample-grid2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.sample-label { margin: 0 0 6px; font-size: 12px; color: var(--app-text-muted); font-weight: 650; }
.sample-io { max-height: 240px; min-height: 64px; }

.problem-detail__divider {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  margin: 0 -3px;
  cursor: col-resize;
  touch-action: none;
  z-index: 2;
}
.problem-detail__divider::before {
  content: '';
  width: 4px;
  height: 56px;
  border-radius: 999px;
  background: var(--app-border);
  transition: background .15s ease, height .15s ease;
}
.problem-detail__divider:hover::before,
.problem-detail__divider:focus-visible::before { background: var(--el-color-primary-light-3); height: 88px; }

.problem-detail__workbench { display: flex; flex-direction: column; gap: 14px; min-width: 0; min-height: 0; }
.editor-shell { flex: 1; display: flex; flex-direction: column; min-height: 260px; }
.editor-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.editor-toolbar__language { width: 150px; }
.editor-toolbar__actions { margin-left: auto; display: flex; gap: 8px; }
.editor-wrap { flex: 1; min-height: 0; }

.sub-table :deep(.el-table__row) { cursor: pointer; }

@media (max-width: 899px) {
  .problem-detail__layout.stacked { display: block; }
  .problem-detail__statement { overflow: visible; padding-right: 0; }
  .problem-detail__divider { display: none; }
  .editor-shell { min-height: 480px; }
  .statement-card__head { flex-direction: column; }
  .sample-grid2 { grid-template-columns: 1fr; }
}
</style>
