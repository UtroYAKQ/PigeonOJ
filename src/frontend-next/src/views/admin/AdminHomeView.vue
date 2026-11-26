<script setup lang="ts">
/**
 * 首页配置（/admin/home）：首页轮播海报 + 系统公告。
 * 独立页面直连两个配置项（site.banners / site.announcement），不经通用配置表格。
 * 海报 = 图片上传 + 标题 + 跳转路径（最多 10 张，顺序即轮播顺序，存 JSONB 数组）；
 * 公告 = Markdown 编辑（展示侧 MarkdownView 渲染，html:false + DOMPurify 白名单）。
 * 保存后刷新公开站点配置，触达壳层与首页（pigeonoj:site-config-change）。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import * as adminApi from '@/api/admin'
import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import PageShell from '@/components/common/PageShell.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import { Button } from '@/components/ui/button'
import { useAppStore } from '@/stores/app'
import { message } from '@/utils/feedback'
import BannerListEditor from './config-components/BannerListEditor.vue'
import { normalizeBanners, toBannerDraft, type BannerDraft } from './config-components/banners'
import { ANNOUNCEMENT_KEY, BANNERS_KEY } from './config-components/config-meta'

const { t } = useI18n()
const appStore = useAppStore()

const loading = ref(false)
const saving = ref(false)
const banners = ref<BannerDraft[]>([])
const announcement = ref('')
/** 配置行 id（保存回写用） */
const bannerRowId = ref('')
const announcementRowId = ref('')

const canSave = computed(() => Boolean(bannerRowId.value || announcementRowId.value))

async function load(): Promise<void> {
  loading.value = true
  try {
    const rows = await adminApi.adminListConfigs('site')
    for (const row of rows) {
      if (row.config_key === BANNERS_KEY) {
        bannerRowId.value = row.id
        banners.value = toBannerDraft(row.config_value)
      } else if (row.config_key === ANNOUNCEMENT_KEY) {
        announcementRowId.value = row.id
        announcement.value = typeof row.config_value === 'string' ? row.config_value : ''
      }
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('config.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  const items: Array<{ id: string; config_value: unknown }> = []
  if (bannerRowId.value) {
    items.push({ id: bannerRowId.value, config_value: normalizeBanners(banners.value) })
  }
  if (announcementRowId.value) {
    items.push({ id: announcementRowId.value, config_value: announcement.value })
  }
  if (!items.length) return

  saving.value = true
  try {
    await adminApi.adminUpdateConfigs(items)
    message.success(t('config.saveSuccess'))
    await load()
    // 首页 / 壳层读公开站点配置：保存后立即生效，并刷新浏览器标签标题
    await appStore.loadSiteConfig()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('config.saveFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <PageShell :title="t('nav.homeConfig')" :description="t('config.homeHint')">
    <template #actions>
      <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
    </template>

    <form class="space-y-8" @submit.prevent="save">
      <section>
        <h2 class="text-lg font-medium">{{ t('config.homeBanners') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('config.homeBannersHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />
        <BannerListEditor v-model="banners" />
      </section>

      <section>
        <div class="h-px bg-border" role="separator" />
        <h2 class="pt-8 text-lg font-medium">{{ t('config.homeAnnouncement') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('config.homeAnnouncementHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />
        <MarkdownEditor
          v-model="announcement"
          min-height="360px"
          :placeholder="t('config.announcementPlaceholder')"
        />
      </section>

      <div class="flex flex-wrap justify-start gap-2 pt-2">
        <Button type="submit" :disabled="saving || !canSave">
          <Loader2 v-if="saving" class="size-4 animate-spin" />
          {{ t('action.save') }}
        </Button>
      </div>
    </form>
  </PageShell>
</template>
