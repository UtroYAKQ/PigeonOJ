<script setup lang="ts">
/**
 * 首页配置（/admin/home）：首页轮播海报 + 系统公告。
 * 独立页面直连两个配置项（site.banners / site.announcement），不经通用配置表格。
 * 海报 = 图片上传（公共图片接口）+ 标题 + 跳转路径，最多 10 张，存 JSONB 数组；
 * 公告 = Markdown 编辑器（md-editor-v3 封装），展示侧经 MarkdownView 渲染
 * （html:false + DOMPurify 白名单，与题面 / 比赛公告同链路）。
 */
import { CircleClose, Plus } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import * as adminApi from '@/api/admin'
import { uploadImage } from '@/api/files'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import { message } from '@/utils/feedback'
import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'

const { t } = useI18n()
const BANNERS_KEY = 'site.banners'
const ANNOUNCEMENT_KEY = 'site.announcement'

interface BannerDraft {
  image: string
  title: string
  link: string
}

const loading = ref(false)
const saving = ref(false)
const banners = ref<BannerDraft[]>([])
const announcement = ref('')
/** 配置行 id（保存回写用） */
const bannerRowId = ref('')
const announcementRowId = ref('')

// 海报上传：单个隐藏 file input，记录当前上传行
const bannerInput = ref<HTMLInputElement | null>(null)
const uploadIndex = ref<number | null>(null)
const uploading = ref(false)

async function load() {
  loading.value = true
  try {
    const rows = await adminApi.adminListConfigs('site')
    for (const row of rows) {
      if (row.config_key === BANNERS_KEY) {
        bannerRowId.value = row.id
        const raw = row.config_value
        banners.value = Array.isArray(raw)
          ? raw.map((b) => ({
              image: String(b?.image ?? ''),
              title: String(b?.title ?? ''),
              link: String(b?.link ?? ''),
            }))
          : []
      } else if (row.config_key === ANNOUNCEMENT_KEY) {
        announcementRowId.value = row.id
        announcement.value = typeof row.config_value === 'string' ? row.config_value : ''
      }
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('config.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)

function addBanner() {
  if (banners.value.length >= 10) {
    message.warning(t('config.bannersMax'))
    return
  }
  banners.value.push({ image: '', title: '', link: '' })
}

function removeBanner(index: number) {
  banners.value.splice(index, 1)
}

function pickImage(index: number) {
  uploadIndex.value = index
  bannerInput.value?.click()
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  const index = uploadIndex.value
  if (!file || index === null || !banners.value[index]) return
  uploading.value = true
  try {
    const result = await uploadImage(file)
    banners.value[index].image = result.url
    message.success(t('common.success'))
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.imageUploadFailed'))
  } finally {
    uploading.value = false
    uploadIndex.value = null
  }
}

async function save() {
  saving.value = true
  try {
    const items = [] as Array<{ id: string; config_value: unknown }>
    if (bannerRowId.value) {
      // 无图片的半成品条目丢弃
      items.push({
        id: bannerRowId.value,
        config_value: banners.value.filter((b) => b.image.trim()),
      })
    }
    if (announcementRowId.value) {
      items.push({ id: announcementRowId.value, config_value: announcement.value })
    }
    if (items.length) await adminApi.adminUpdateConfigs(items)
    message.success(t('config.saveSuccess'))
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('config.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <WorkbenchShell :title="t('nav.homeConfig')">
    <template #header-extra>
      <div class="homecfg-actions">
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
        <n-button type="primary" :loading="saving" @click="save">
          {{ t('action.save') }}
        </n-button>
      </div>
    </template>

    <div class="homecfg">
      <!-- 左：海报列表（顺序即轮播顺序，点击缩略图上传/更换图片） -->
      <section class="homecfg-section">
        <header class="homecfg-head">
          <div>
            <h3 class="homecfg-title">{{ t('config.homeBanners') }}</h3>
            <p class="homecfg-sub">{{ t('config.homeBannersHint') }}</p>
          </div>
          <n-button size="small" :disabled="banners.length >= 10" @click="addBanner">
            + {{ t('config.addBanner') }}
          </n-button>
        </header>

        <transition-group name="homecfg" tag="div" class="homecfg-list">
          <div v-for="(banner, index) in banners" :key="index" class="homecfg-banner">
            <span class="homecfg-order">{{ index + 1 }}</span>
            <button
              type="button"
              class="homecfg-thumb"
              :class="{ 'homecfg-thumb--empty': !banner.image }"
              :disabled="uploadIndex === index && uploading"
              @click="pickImage(index)"
            >
              <img v-if="banner.image" :src="banner.image" alt="" />
              <span v-else class="homecfg-thumb-placeholder">
                <n-icon :component="Plus" />
                {{ t('config.uploadImage') }}
              </span>
              <span v-if="uploadIndex === index && uploading" class="homecfg-thumb-loading">
                {{ t('common.loading') }}
              </span>
            </button>
            <div class="homecfg-banner-fields">
              <n-input
                v-model:value="banner.title"
                :placeholder="t('config.bannerTitle')"
                maxlength="60"
              />
              <n-input
                v-model:value="banner.link"
                :placeholder="t('config.bannerLink')"
                maxlength="255"
              />
            </div>
            <n-button
              size="tiny"
              quaternary
              type="error"
              class="homecfg-remove"
              :aria-label="t('config.removeBanner')"
              @click="removeBanner(index)"
            >
              <template #icon><n-icon :component="CircleClose" /></template>
            </n-button>
          </div>
        </transition-group>

        <div v-if="!banners.length" class="homecfg-empty">
          {{ t('config.bannersEmpty') }}
        </div>

        <input
          ref="bannerInput"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          hidden
          @change="onFileChange"
        />
      </section>

      <!-- 右：系统公告（Markdown 编辑器），拉伸与左栏等高 -->
      <section class="homecfg-section homecfg-section--announcement">
        <header class="homecfg-head">
          <div>
            <h3 class="homecfg-title">{{ t('config.homeAnnouncement') }}</h3>
            <p class="homecfg-sub">{{ t('config.homeAnnouncementHint') }}</p>
          </div>
        </header>
        <MarkdownEditor
          v-model="announcement"
          class="homecfg-announcement"
          min-height="100%"
          :placeholder="t('config.announcementPlaceholder')"
        />
      </section>
    </div>
  </WorkbenchShell>
</template>

<style scoped>
/* 顶部动作区：刷新 + 保存 */
.homecfg-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
/* 左海报 / 右公告两栏，各栏拉伸撑满 */
.homecfg {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(300px, 1fr);
  gap: 16px;
  align-items: stretch;
  min-height: calc(100dvh - 200px);
}
.homecfg-section {
  display: grid;
  gap: 14px;
  align-content: start;
  padding: 20px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-card-bg, #fff);
}
/* 公告卡：纵向布局（标题 + 编辑器拉伸填满剩余高度） */
.homecfg-section--announcement {
  grid-template-rows: auto minmax(0, 1fr);
}
/* 公告编辑器撑满卡片剩余高度（高度经 min-height='100%' 交给 md-editor-v3；
   窄屏单栏时以 220px 保底） */
.homecfg-announcement {
  min-height: 100%;
}

.homecfg-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.homecfg-title {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.homecfg-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.homecfg-list {
  display: grid;
  gap: 10px;
}
/* 海报行：序号徽标 + 16:9 缩略图 + 字段列 + 悬停删除 */
.homecfg-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-card-bg, #fff);
  transition: border-color 0.15s ease;
}
.homecfg-banner:hover {
  border-color: var(--app-text-muted);
}
.homecfg-order {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 650;
  color: var(--app-text-secondary);
  background: var(--app-muted-bg);
}
.homecfg-thumb {
  position: relative;
  width: 160px;
  aspect-ratio: 16 / 9;
  flex-shrink: 0;
  overflow: hidden;
  padding: 0;
  border: 1px dashed var(--app-border-strong, var(--app-border));
  border-radius: 4px;
  background: var(--app-muted-bg);
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.homecfg-thumb:hover {
  border-color: var(--app-primary);
}
.homecfg-thumb img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.homecfg-thumb-placeholder {
  display: grid;
  place-items: center;
  gap: 2px;
  width: 100%;
  height: 100%;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.homecfg-thumb-loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 12px;
  color: #fff;
  background: rgba(0, 0, 0, 0.45);
}
.homecfg-banner-fields {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 8px;
}
.homecfg-remove {
  opacity: 0;
  transition: opacity 0.15s ease;
}
.homecfg-banner:hover .homecfg-remove,
.homecfg-remove:focus-visible {
  opacity: 1;
}
/* 空态与增删过渡 */
.homecfg-empty {
  padding: 20px;
  text-align: center;
  font-size: 12px;
  color: var(--app-text-secondary);
  border: 1px dashed var(--app-border);
  border-radius: 6px;
}
.homecfg-enter-active,
.homecfg-leave-active {
  transition: opacity 0.18s ease;
}
.homecfg-enter-from,
.homecfg-leave-to {
  opacity: 0;
}
@media (max-width: 960px) {
  .homecfg {
    grid-template-columns: 1fr;
    min-height: 0;
  }
  .homecfg-announcement {
    min-height: 260px;
  }
}
@media (max-width: 640px) {
  .homecfg-banner {
    flex-wrap: wrap;
  }
  .homecfg-banner-fields {
    flex-basis: 100%;
    order: 3;
  }
  .homecfg-remove {
    opacity: 1;
  }
}
</style>
