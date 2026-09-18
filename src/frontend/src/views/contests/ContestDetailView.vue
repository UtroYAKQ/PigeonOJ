<script setup lang="ts">
/**
 * 比赛详情：主页（hero + 倒计时条 + 数据瓦片 + 时间轴 + 说明）/ 题目 / 榜单 / 提交记录 四个 tab。
 * 本组件只保留数据装配（详情加载 / 翻页时钟 / 报名 / 管理入口）与 tab 切换；
 * 各模块面板见 ./components/*Panel.vue（题目 / 榜单 / 提交记录各自持有列表数据与加载）。
 * 榜单封榜展示冻结快照，解冻为 admin 手动操作（重算回填封榜期结果）；
 * 提交记录比赛期间仅管理角色（can_manage）可见，赛后对所有登录用户开放。
 */
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { MoreFilled } from '@element-plus/icons-vue'
import type { DropdownOption } from 'naive-ui'

import WorkbenchShell from '@/components/WorkbenchShell.vue'
import BaseAvatar from '@/components/BaseAvatar.vue'
import { getContest, registerContest } from '@/api/contests'
import { getTeamContest, registerTeamContest } from '@/api/teams'
import { message } from '@/utils/feedback'
import ContestHomePanel from './components/ContestHomePanel.vue'
import ContestProblemsPanel from './components/ContestProblemsPanel.vue'
import ContestBoardPanel from './components/ContestBoardPanel.vue'
import ContestSubmissionsPanel from './components/ContestSubmissionsPanel.vue'
import type { ContestDetail } from '@/types'

const boardPanel = ref<InstanceType<typeof ContestBoardPanel> | null>(null)

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const detail = ref<ContestDetail | null>(null)
const registering = ref(false)
type ContestTab = 'home' | 'problems' | 'board' | 'submissions'
const TAB_KEYS: ContestTab[] = ['home', 'problems', 'board', 'submissions']
function tabFromQuery(raw: unknown): ContestTab {
  const value = typeof raw === 'string' ? raw : ''
  return (TAB_KEYS as string[]).includes(value) ? (value as ContestTab) : 'home'
}
/** 模块 tab（题目 / 榜单 / 提交记录）可见性：管理角色随时可见（编排 / 巡查）；
 *  赛前对非管理角色隐藏；比赛期间仅已报名者可见（未报名者从主页 tab 报名）；
 *  赛后对所有用户开放（看题 / 补题，contests.md 第 2 / 6 条口径） */
const moduleTabsVisible = computed(() => {
  const d = detail.value
  if (!d) return false
  if (d.can_manage) return true
  if (d.status === 'scheduled') return false
  if (d.status === 'running') return d.my_registration === 'registered'
  return true
})
/** 被赛前隐藏的模块 tab 一律回落主页（直链 ?tab=… / 查询参数同步共用） */
function clampTab(tab: ContestTab): ContestTab {
  return tab === 'home' || moduleTabsVisible.value ? tab : 'home'
}
const activeTab = ref<ContestTab>(clampTab(tabFromQuery(route.query.tab)))

/** 比赛 id：全局路由取 params.id，团队上下文路由取 params.cid */
const contestId = computed(() => String(route.params.cid ?? route.params.id))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    detail.value = await (teamId.value
      ? getTeamContest(teamId.value, contestId.value)
      : getContest(contestId.value))
  } catch (error) {
    if (!silent) message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (!silent) loading.value = false
  }
}

watch(
  () => route.query.tab,
  (raw) => {
    const next = clampTab(tabFromQuery(raw))
    if (next !== activeTab.value) activeTab.value = next
  },
)

// 详情就绪 / 状态变化后校正：当前 tab 若已被赛前隐藏（直链进入）回落主页
watch(moduleTabsVisible, (visible) => {
  if (!visible && activeTab.value !== 'home') activeTab.value = 'home'
})

// ---------------- 主页：时钟（进行中榜单轮询收敛在榜单面板） ----------------

let clockTimer: number | null = null

function startTimers() {
  if (clockTimer !== null) return // 已在运行（如 activated 重复触发）
  clockTimer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1_000)
}

onMounted(() => {
  void load()
  startTimers()
})
// KeepAlive 缓存页：被切走时停表（后台不空转），返回时恢复
onDeactivated(() => {
  if (clockTimer !== null) {
    window.clearInterval(clockTimer)
    clockTimer = null
  }
})
onActivated(() => {
  // keepAlive 返回：重拉详情（编排题目后返回不显示旧空数据），恢复计时器
  if (detail.value) void load()
  startTimers()
})
onBeforeUnmount(() => {
  if (clockTimer !== null) {
    window.clearInterval(clockTimer)
    clockTimer = null
  }
})

async function register() {
  if (!detail.value) return
  registering.value = true
  try {
    await (teamId.value
      ? registerTeamContest(teamId.value, detail.value.id)
      : registerContest(detail.value.id))
    message.success(t('common.success'))
    await load(true)
    if (activeTab.value === 'board') boardPanel.value?.refresh()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    registering.value = false
  }
}

const statusMeta = computed(() => {
  const map = {
    running: { label: t('contests.statusRunning'), type: 'success' as const },
    scheduled: { label: t('contests.statusScheduled'), type: 'info' as const },
    finished: { label: t('contests.statusFinished'), type: 'default' as const },
  }
  return map[detail.value?.status ?? 'scheduled']
})

const manageOptions = computed<DropdownOption[]>(() => {
  if (!detail.value?.can_manage) return []
  return [
    {
      key: 'edit',
      label: t('contests.detail.manage'),
      disabled: detail.value.status !== 'scheduled',
    },
    { key: 'tools', label: t('contests.tools.title') },
  ]
})

function onManageSelect(key: string | number) {
  const cid = contestId.value
  const team = teamId.value
  if (key === 'edit') {
    if (detail.value?.status !== 'scheduled') return
    void router.push(
      team ? `/teams/${team}/contests/${cid}/edit/basic` : `/admin/contests/${cid}/edit/basic`,
    )
    return
  }
  if (key === 'tools') {
    void router.push(team ? `/teams/${team}/contests/${cid}/tools` : `/admin/contests/${cid}/tools`)
  }
}

// ---------------- 主页：时钟与倒计时 ----------------

/** 每秒自增的"当前时间"（驱动翻页时钟倒计时，不重拉数据） */
const nowTick = ref(Date.now())

/** 毫秒 → 翻页时钟分段（天:时:分:秒，零填充） */
function toSegments(ms: number): { value: string; unit: string }[] {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return [
    { value: pad(days), unit: t('contests.detail.unitDay') },
    { value: pad(hours), unit: t('contests.detail.unitHour') },
    { value: pad(minutes), unit: t('contests.detail.unitMinute') },
    { value: pad(seconds), unit: t('contests.detail.unitSecond') },
  ]
}

/** Hero 翻页时钟：未开始 → 距开始；进行中 → 距结束；结束 → null（恒定文案） */
const digitalCountdown = computed(() => {
  const d = detail.value
  if (!d) return null
  const now = nowTick.value
  const start = new Date(d.start_time).getTime()
  const end = new Date(d.end_time).getTime()
  if (d.status === 'running') {
    return { label: t('contests.detail.endsIn'), segments: toSegments(end - now) }
  }
  if (d.status === 'finished' || now >= end) {
    return null
  }
  return { label: t('contests.detail.startsIn'), segments: toSegments(start - now) }
})
</script>

<template>
  <WorkbenchShell>
    <div class="contest-fill">
      <!-- 加载骨架 / 失败态：背景板位置占位（团队页同款，不把内容包进 n-spin） -->
      <div v-if="!detail" class="hero" :class="loading ? 'hero--skeleton' : 'hero--failed'">
        <div v-if="loading" class="hero-skeleton">
          <n-skeleton height="64px" width="64px" :sharp="false" round />
          <div class="hero-skeleton__lines">
            <n-skeleton text style="width: 32%" />
            <n-skeleton text style="width: 58%" />
          </div>
        </div>
        <n-empty v-else :description="t('common.loadFailed')" size="large">
          <template #extra>
            <n-button @click="load()">{{ t('action.refresh') }}</n-button>
          </template>
        </n-empty>
      </div>

      <template v-else>
        <!-- ======== Hero 背景板（团队页同款：中性底 + 主色几何点缀） ======== -->
        <section class="hero">
          <div class="hero__banner" aria-hidden="true">
            <span class="hero__orb"></span>
            <span class="hero__ring"></span>
          </div>
          <div class="hero__body">
            <div class="hero__row hero__row--top">
              <div class="hero__logo">
                <BaseAvatar
                  kind="contest"
                  :src="detail.logo"
                  :name="detail.title"
                  :size="88"
                  :round="false"
                  :radius="10"
                />
              </div>
              <div class="hero__id">
                <h1 class="hero__title">{{ detail.title }}</h1>
                <div class="hero__chips">
                  <span class="hero__chip" :class="`hero__chip--${statusMeta.type}`">
                    <span
                      v-if="detail.status === 'running'"
                      class="hero__pulse"
                      aria-hidden="true"
                    ></span>
                    {{ statusMeta.label }}
                  </span>
                  <span class="hero__chip">{{ detail.rule_type }}</span>
                  <span
                    v-if="detail.my_registration === 'registered'"
                    class="hero__chip hero__chip--ok"
                  >
                    {{ t('contests.detail.registered') }}
                  </span>
                  <span v-if="detail.board_frozen" class="hero__chip hero__chip--warning">
                    {{ t('contests.boardFrozenTag') }}
                  </span>
                </div>
                <!-- 统计行：题目数 / 报名数（标题正下方） -->
                <div class="hero__meta">
                  <span>
                    {{ t('contests.detail.problems') }}
                    <strong class="hero__meta-num">{{ detail.problem_count }}</strong>
                  </span>
                  <span class="hero__dot" aria-hidden="true">·</span>
                  <span>
                    {{ t('contests.detail.registeredCount') }}
                    <strong class="hero__meta-num">{{ detail.registered_count }}</strong>
                  </span>
                </div>
              </div>
              <!-- 动作区：翻页时钟（未开始 → 距开始；进行中 → 距结束）+ 报名 -->
              <div class="hero__actions">
                <div
                  v-if="digitalCountdown"
                  class="hero__clock"
                  :class="`hero__clock--${detail.status}`"
                >
                  <span class="hero__clock-label">{{ digitalCountdown.label }}</span>
                  <div
                    class="flip-clock"
                    :aria-label="`${digitalCountdown.label} ${digitalCountdown.segments
                      .map((s) => s.value)
                      .join(':')}`"
                  >
                    <template v-for="(seg, gi) in digitalCountdown.segments" :key="gi">
                      <span v-if="gi > 0" class="flip-clock__colon" aria-hidden="true">:</span>
                      <span class="flip-clock__group">
                        <span
                          v-for="(ch, ci) in seg.value"
                          :key="`${gi}-${ci}-${ch}`"
                          class="flip-clock__card"
                          >{{ ch }}</span
                        >
                      </span>
                    </template>
                  </div>
                </div>
                <span v-else class="hero__clock-label">{{ t('contests.detail.contestOver') }}</span>
                <n-button
                  v-if="detail.can_register"
                  type="primary"
                  size="large"
                  :loading="registering"
                  @click="register"
                >
                  {{ t('contests.detail.register') }}
                </n-button>
                <n-dropdown
                  v-if="manageOptions.length"
                  trigger="click"
                  placement="bottom-end"
                  :options="manageOptions"
                  @select="onManageSelect"
                >
                  <n-button circle quaternary size="large" :aria-label="t('teams.detail.more')">
                    <template #icon>
                      <n-icon :component="MoreFilled" />
                    </template>
                  </n-button>
                </n-dropdown>
              </div>
            </div>
          </div>
        </section>

        <!-- ======== 内容模块（tab 线条直连内容） ========
             display-directive="show"：pane 挂载后常驻（仅 display 切换），
             避免 if 模式反复卸载重建在 v-show 互斥节点上引发补丁错位（内容丢失）；
             榜单 / 提交记录面板经 active 属性接收激活态，各自懒加载 -->
        <section class="module-area">
          <n-tabs type="line" v-model:value="activeTab" class="module-tabs">
            <!-- ======== 主页 ======== -->
            <n-tab-pane name="home" :tab="t('contests.detail.tabHome')" display-directive="show">
              <ContestHomePanel :detail="detail" />
            </n-tab-pane>

            <!-- ======== 题目（赛前 / 未报名对非管理角色隐藏） ======== -->
            <n-tab-pane
              v-if="moduleTabsVisible"
              name="problems"
              :tab="t('contests.detail.tabProblems')"
              display-directive="show"
            >
              <ContestProblemsPanel :detail="detail" />
            </n-tab-pane>

            <!-- ======== 榜单（赛前 / 未报名对非管理角色隐藏） ======== -->
            <n-tab-pane
              v-if="moduleTabsVisible"
              name="board"
              :tab="t('contests.detail.tabBoard')"
              display-directive="show"
            >
              <ContestBoardPanel
                ref="boardPanel"
                :detail="detail"
                :active="activeTab === 'board'"
              />
            </n-tab-pane>

            <!-- ======== 提交记录（赛前 / 未报名对非管理角色隐藏） ======== -->
            <n-tab-pane
              v-if="moduleTabsVisible"
              name="submissions"
              :tab="t('contests.detail.tabSubmissions')"
              display-directive="show"
            >
              <ContestSubmissionsPanel :detail="detail" :active="activeTab === 'submissions'" />
            </n-tab-pane>
          </n-tabs>
        </section>
      </template>
    </div>
  </WorkbenchShell>
</template>

<style scoped>
/* ---- 通栏填充 + 一屏锁定：卡片内容 → 填充区 → 模块区 → tabs → pane 纵向伸展，
     表格区（table-fill / flex-height）撑满剩余高度、表体内部滚动，分页条恒贴底 ---- */
/* 通栏填充：抵消应用壳卡片默认 padding，Hero 背景板直接铺到卡片边缘 */
.contest-fill {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin: calc(-1 * var(--n-padding-top, 20px)) calc(-1 * var(--n-padding-left, 24px))
    calc(-1 * var(--n-padding-bottom, 24px));
}

/* 加载骨架 / 失败态：占位在背景板位置 */
.hero--skeleton {
  padding: 28px 32px;
}
.hero-skeleton {
  display: flex;
  align-items: center;
  gap: 16px;
}
.hero-skeleton__lines {
  flex: 1;
  display: grid;
  gap: 8px;
  max-width: 420px;
}
.hero--failed {
  padding: 56px 32px;
  display: flex;
  justify-content: center;
}

/* ======== Hero 背景板：中性底 + 主色几何（团队页同款规则） ========
   底色比卡片深一档（surface-muted），主色只以「被裁切的圆」出现：
   右上实心巨弧 + 右下描边环，画面内不留完整圆形。 */
.hero {
  position: relative;
  flex-shrink: 0;
  border-bottom: 1px solid var(--app-border);
  background:
    radial-gradient(
      90% 220% at 97% 112%,
      color-mix(in srgb, var(--app-primary) 6%, transparent) 0%,
      transparent 62%
    ),
    radial-gradient(
      120% 180% at 0% 0%,
      color-mix(in srgb, var(--app-primary) 5%, transparent) 0%,
      transparent 52%
    ),
    var(--app-surface-muted, #f7f7fa);
  overflow: hidden;
}
/* 巨圆：圆心落在上沿外 252px，只露出底部一弧；
   填充用径向渐变（20% → 5% → 0），边缘化开，避免出现生硬的色块边界 */
.hero__orb {
  position: absolute;
  width: 340px;
  height: 340px;
  border-radius: 999px;
  right: 7%;
  top: -252px;
  background: radial-gradient(
    circle at 50% 50%,
    color-mix(in srgb, var(--app-primary) 20%, transparent) 0%,
    color-mix(in srgb, var(--app-primary) 5%, transparent) 58%,
    transparent 74%
  );
}
/* 描边环：被右侧与底部各裁一截，与上方实心弧形成一虚一实 */
.hero__ring {
  position: absolute;
  width: 228px;
  height: 228px;
  border-radius: 999px;
  right: -104px;
  bottom: -120px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 24%, transparent);
}
.hero__body {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 26px 32px 20px;
  max-width: 1680px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}
/* 第一行：logo + 标题/标签/统计 + 翻页时钟/报名动作区 */
.hero__row--top {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
/* 比赛Logo：团队头像同款描边与投影；尺寸 / 圆角 / 回退图由 BaseAvatar 承担 */
.hero__logo {
  flex-shrink: 0;
  border: 3px solid var(--app-card-bg, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 8%);
}
.hero__id {
  flex: 1;
  min-width: 240px;
  display: grid;
  gap: 8px;
}
.hero__title {
  margin: 0;
  line-height: 1.2;
  font-size: 22px;
  font-weight: 700;
  color: var(--app-text);
  margin-right: 4px;
}
.hero__chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
/* 标签：直角矩形（不用圆角药丸） */
.hero__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-secondary);
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border);
}
.hero__chip--success {
  color: var(--app-success, #18a058);
  border-color: color-mix(in srgb, var(--app-success, #18a058) 45%, transparent);
  background: color-mix(in srgb, var(--app-success, #18a058) 8%, var(--app-card-bg, #fff));
}
.hero__chip--info {
  color: var(--app-info, #2080f0);
  border-color: color-mix(in srgb, var(--app-info, #2080f0) 45%, transparent);
  background: color-mix(in srgb, var(--app-info, #2080f0) 8%, var(--app-card-bg, #fff));
}
.hero__chip--default {
  color: var(--app-text-secondary);
}
.hero__chip--warning {
  color: var(--app-warning, #f0a020);
  border-color: color-mix(in srgb, var(--app-warning, #f0a020) 45%, transparent);
  background: color-mix(in srgb, var(--app-warning, #f0a020) 8%, var(--app-card-bg, #fff));
}
.hero__chip--ok {
  color: var(--app-success, #18a058);
  border-color: color-mix(in srgb, var(--app-success, #18a058) 45%, transparent);
  background: color-mix(in srgb, var(--app-success, #18a058) 8%, var(--app-card-bg, #fff));
}
.hero__pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  animation: hero-pulse 1.6s ease-in-out infinite;
}
@keyframes hero-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 45%, transparent);
  }
  60% {
    box-shadow: 0 0 0 4px transparent;
  }
}
/* 统计行：题目数 / 报名数 / 封榜时间（团队 Hero meta 同款排版） */
.hero__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--app-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.hero__dot {
  opacity: 0.5;
}
.hero__meta-num {
  font-weight: 600;
  color: var(--app-text);
}
/* 动作区：报名 / 刷新；窄屏自动换行 */
.hero__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-left: auto;
}
/* 翻页时钟：报名按钮左侧（hero__actions 内 margin-left:auto 已右对齐） */
.hero__clock {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hero__clock-label {
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.02em;
  color: var(--app-text-secondary);
  text-transform: uppercase;
}
/* 翻页时钟：每组 = 数字卡 ×2，卡片中缝横线模拟翻页轴 */
.flip-clock {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.flip-clock__colon {
  font-size: 24px;
  font-weight: 750;
  color: var(--app-text-secondary);
  line-height: 1;
  transform: translateY(-2px);
}
.flip-clock__group {
  display: inline-flex;
  gap: 3px;
  perspective: 220px;
}
.flip-clock__card {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 54px;
  border-radius: 6px;
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border);
  box-shadow: 0 2px 5px rgb(0 0 0 / 10%);
  font-size: 28px;
  font-weight: 750;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: var(--app-text);
  overflow: hidden;
  /* 数字变化时卡片重挂载（key 绑定数字值），翻页动画重放 */
  animation: flip-fold 0.45s cubic-bezier(0.2, 0.7, 0.3, 1);
}
/* 翻页：新数字自上折下（rotateX 88° → 0，透视原点在卡顶） */
@keyframes flip-fold {
  0% {
    transform: rotateX(-88deg);
    opacity: 0.4;
  }
  100% {
    transform: rotateX(0deg);
    opacity: 1;
  }
}
/* 翻页轴中缝：横贯卡片的半透明分割线 */
.flip-clock__card::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: color-mix(in srgb, var(--app-border) 70%, transparent);
}
.hero__clock--scheduled .flip-clock__card {
  color: var(--app-info, #2080f0);
}
.hero__clock--running .flip-clock__card {
  color: var(--app-success, #18a058);
}

/* ---- 模块区：tab 线条直连内容，无卡片外框（团队页同款） ---- */
.module-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tabs-nav) {
  padding: 4px 32px 0;
  flex-shrink: 0;
}
.module-tabs :deep(.n-tabs-tab) {
  font-size: 14px;
  padding: 12px 6px;
}
/* 非 animated 模式 naive 不渲染 pane-wrapper，pane 直接挂在 .n-tabs 下 */
.module-tabs :deep(.n-tabs-pane-wrapper),
.module-tabs :deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tab-pane) {
  padding: 16px 32px 20px;
}
</style>
