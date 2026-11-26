<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { buildCrumbs } from '@/router/crumbs'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const crumbs = computed(() => buildCrumbs(route, (key) => t(key)))
</script>

<template>
  <nav
    v-if="crumbs.length"
    class="flex min-w-0 items-center gap-1.5 text-[13px]"
    aria-label="Breadcrumb"
  >
    <template v-for="(crumb, index) in crumbs" :key="`${index}-${crumb.label}`">
      <span v-if="index > 0" class="text-muted-foreground/50" aria-hidden="true">/</span>
      <button
        v-if="crumb.to"
        type="button"
        class="truncate rounded-sm px-0.5 text-muted-foreground transition-colors hover:text-foreground"
        @click="router.push(crumb.to)"
      >
        {{ crumb.label }}
      </button>
      <span v-else class="truncate font-medium text-foreground" aria-current="page">
        {{ crumb.label }}
      </span>
    </template>
  </nav>
</template>
