<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import BrandMark from '@/layout/BrandMark.vue'
import { useAppStore } from '@/stores/app'

defineProps<{ title: string; subtitle?: string }>()

const appStore = useAppStore()
const { t } = useI18n()
const siteName = computed(() => appStore.siteName)
</script>

<template>
  <div
    class="grid min-h-dvh bg-background text-foreground lg:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)]"
  >
    <aside
      class="relative hidden overflow-hidden border-r border-border bg-surface lg:flex lg:flex-col"
    >
      <div class="dot-grid pointer-events-none absolute inset-0 opacity-[0.55]" />
      <div
        class="pointer-events-none absolute -right-32 -top-32 size-[420px] rounded-full bg-brand-soft blur-3xl"
      />

      <div class="relative flex flex-1 flex-col p-10 xl:p-14">
        <router-link to="/" class="flex w-fit items-center gap-2.5 text-[14px] font-semibold">
          <BrandMark size="sm" />
          <span>{{ siteName }}</span>
        </router-link>

        <div class="my-auto max-w-[520px] py-16">
          <p class="text-[12.5px] font-medium tracking-[0.18em] text-brand">
            {{ t('auth.heroKicker') }}
          </p>
          <h1
            class="mt-4 max-w-[15ch] text-balance text-[34px] font-semibold leading-[1.2] tracking-tight"
          >
            {{ t('auth.heroTitle') }}
          </h1>
          <p class="mt-4 max-w-[42ch] text-[14px] leading-7 text-muted-foreground">
            {{ t('home.intro') }}
          </p>

          <div
            class="mt-10 grid max-w-[420px] gap-3 border-t border-border pt-6 text-[13px] text-muted-foreground"
          >
            <p class="flex items-center justify-between gap-6">
              <span>{{ t('auth.featureLanguages') }}</span>
              <span class="font-mono text-foreground">C++17 · Python 3.12 · Java 21</span>
            </p>
            <p class="flex items-center justify-between gap-6">
              <span>{{ t('auth.featureRuntime') }}</span>
              <span class="text-foreground">{{ t('auth.featureRuntimeValue') }}</span>
            </p>
          </div>
        </div>

        <p class="text-[11.5px] text-muted-foreground">{{ siteName }} · {{ t('app.tagline') }}</p>
      </div>
    </aside>

    <main class="flex flex-col px-6 py-8 sm:px-10">
      <router-link
        to="/"
        class="flex w-fit items-center gap-2.5 text-[13.5px] font-semibold lg:hidden"
      >
        <BrandMark size="sm" />
        <span>{{ siteName }}</span>
      </router-link>

      <div class="fade-in m-auto w-full max-w-[336px]">
        <header>
          <h2 class="text-[26px] font-semibold leading-tight tracking-tight">{{ title }}</h2>
          <p v-if="subtitle" class="mt-2 text-[13px] leading-6 text-muted-foreground">
            {{ subtitle }}
          </p>
        </header>
        <slot />
      </div>

      <p class="pt-10 text-center text-[11px] text-muted-foreground lg:text-right">
        {{ siteName }}
      </p>
    </main>
  </div>
</template>
