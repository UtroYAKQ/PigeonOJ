<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getProblem } from '@/api/problems'
import { message } from '@/utils/feedback'
import { useSplitPane } from '@/composables/useSplitPane'
import type { ProblemDetailEx } from '@/types'
import VerifyPublishPanel from '@/components/problem/VerifyPublishPanel.vue'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import WizardShell from '@/components/WizardShell.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// 与题库详情页 / 邀请验题页同款可拖拽分栏（比例共享持久化；窄屏自动上下堆叠）
const { isDesktop, splitRef, layoutStyle, startResize, resetSplit, updateSplitHeight } =
  useSplitPane()

const loading = ref(false)
const problemId = String(route.params.id)
/** 完整详情（含验题状态），供「验题与发布」面板使用 */
const detail = ref<ProblemDetailEx | null>(null)
/** 面板实例：发布按钮在向导底栏，动作与门禁状态经 expose 提升 */
const verifyPanel = ref<InstanceType<typeof VerifyPublishPanel> | null>(null)
const publishing = computed(() => verifyPanel.value?.publishing ?? false)
const publishBlocked = computed(() => verifyPanel.value?.blocked ?? true)

/** 数据到位后实测可用高度并锁定分栏（内联像素高，左栏因此可独立滚动） */
watch(detail, () => nextTick(updateSplitHeight))

function onPublish() {
  verifyPanel.value?.publish()
}

async function loadExisting() {
  loading.value = true
  try {
    const loaded: ProblemDetailEx = await getProblem(problemId)
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    detail.value = loaded
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    router.push('/admin/problems')
  } finally {
    loading.value = false
  }
}

function goPrev() {
  router.push(`/admin/problems/${problemId}/edit/cases`)
}
function cancelEdit() {
  // 未发布离开：草稿保留，可随时从管理工作台继续
  router.push('/admin/problems')
}
function onPublished() {
  // 发布成功后回到管理工作台（面板内已提示；前台详情页不承载管理动线）
  router.push('/admin/problems')
}

onMounted(() => {
  nextTick(updateSplitHeight)
  void loadExisting()
})
</script>

<template>
  <div class="page-fill">
    <WizardShell :step="3" :title="t('problems.wizard.verifyPublish')">
      <template #actions>
        <n-button size="small" :disabled="loading" @click="goPrev">
          {{ t('problems.wizard.prev') }}
        </n-button>
        <n-tooltip trigger="hover" placement="top" :disabled="!publishBlocked">
          <template #trigger>
            <n-button
              type="primary"
              size="small"
              :loading="publishing"
              :disabled="publishBlocked || loading"
              @click="onPublish"
            >
              {{ t('problems.detail.publish') }}
            </n-button>
          </template>
          {{ t('problems.manage.publishNeedVerified') }}
        </n-tooltip>
        <n-button size="small" quaternary @click="cancelEdit">{{ t('action.cancel') }}</n-button>
      </template>

      <!-- 卡片内平铺双栏：stage → spin-content → vf-layout 逐层吃满剩余高度 -->
      <n-spin :show="loading" class="vf-stage">
        <div
          v-if="detail"
          ref="splitRef"
          class="vf-layout"
          :class="{ stacked: !isDesktop }"
          :style="layoutStyle"
        >
          <!-- 左：题面（标题元信息 + 正文整体独立滚动） -->
          <section class="vf-statement">
            <ProblemMetaBar :problem="detail" show-title />
            <div class="vf-body">
              <ProblemStatement :problem="detail" :show-solution="false" />
            </div>
          </section>

          <!-- 可拖拽分隔条（双击复位，比例与详情页共享持久化） -->
          <div
            class="vf-divider"
            role="separator"
            aria-orientation="vertical"
            :aria-label="t('problems.detail.resizeHint')"
            :title="t('problems.detail.resizeHint')"
            @pointerdown="startResize"
            @dblclick="resetSplit"
          />

          <!-- 右：验题代码编辑器工作台（面板根节点即网格第三列） -->
          <VerifyPublishPanel
            ref="verifyPanel"
            :problem="detail"
            @refresh="loadExisting"
            @published="onPublished"
          />
        </div>
      </n-spin>
    </WizardShell>
  </div>
</template>

<style scoped>
/* 分栏高度不依赖 CSS 高度链：数据到位后由 updateSplitHeight() 实测剩余空间
   写入内联像素高（layoutStyle.height），对卡片头 / spin 等任意父级结构都成立，
   左栏题面因此始终内部滚动；窗口缩放与语言切换由 useSplitPane 内置监听跟进 */
/* 拉伸链作为内联高度生效前的兜底 */
.vf-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.vf-stage :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 三列网格：左题面（--split 比例）+ 可拖拽分隔条 + 右编辑器 */
.vf-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(300px, var(--split, 50%)) auto minmax(360px, 1fr);
  align-items: stretch;
  gap: 4px;
}

/* 左：题面（独立滚动） */
.vf-statement {
  overflow-y: auto;
  min-width: 0;
  min-height: 0;
  padding-right: 6px;
}
.vf-body {
  margin-top: 14px;
}

/* 可拖拽分隔条：细长手柄，hover / 聚焦变主色（样式对齐详情页） */
.vf-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  margin: 0 -3px;
  cursor: col-resize;
  touch-action: none;
  z-index: 2;
}
.vf-divider::before {
  content: '';
  width: 4px;
  height: 56px;
  border-radius: var(--app-radius-sm, 4px);
  background: var(--app-border);
  transition: background-color 0.15s ease;
}
.vf-divider:hover::before,
.vf-divider:focus-visible::before {
  background: var(--app-primary);
}

@media (max-width: 899px) {
  .vf-stage,
  .vf-stage :deep(.n-spin-content) {
    flex: none;
  }
  .vf-layout.stacked {
    display: block;
  }
  .vf-statement {
    overflow: visible;
    padding-right: 0;
  }
  .vf-divider {
    display: none;
  }
}
</style>
