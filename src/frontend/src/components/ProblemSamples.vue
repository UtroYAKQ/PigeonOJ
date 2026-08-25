<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  samples: Array<{ name: string; input: string; output: string }>
}>()

const { t } = useI18n()

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    /* 静默 */
  }
}
</script>

<template>
  <div v-if="samples.length" class="samples">
    <div v-for="(sample, index) in samples" :key="index" class="sample-block">
      <div class="sample-block__head">
        <strong>#{{ index + 1 }} {{ sample.name }}</strong>
        <n-button text size="small" @click="copyText(sample.input)">
          {{ t('problems.detail.copyInput') }}
        </n-button>
      </div>
      <div class="sample-grid2">
        <div>
          <p class="sample-label">{{ t('problems.detail.stdin') }}</p>
          <pre class="result-box sample-io">{{
            sample.input || t('problems.detail.noOutput')
          }}</pre>
        </div>
        <div>
          <p class="sample-label">{{ t('problems.detail.expected') }}</p>
          <pre class="result-box sample-io">{{
            sample.output || t('problems.detail.noOutput')
          }}</pre>
        </div>
      </div>
    </div>
  </div>
  <n-empty v-else size="small" :description="t('problems.detail.noSamples')" />
</template>

<style scoped>
.samples {
  display: grid;
  gap: 14px;
}
.sample-block {
  border: 1px solid var(--app-border);
  border-radius: 6px;
  padding: 12px;
  background: var(--app-muted-bg);
}
.sample-block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.sample-grid2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.sample-label {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--app-text-secondary);
  font-weight: 500;
}
.sample-io {
  max-height: 240px;
  min-height: 64px;
}
@media (max-width: 899px) {
  .sample-grid2 {
    grid-template-columns: 1fr;
  }
}
</style>
