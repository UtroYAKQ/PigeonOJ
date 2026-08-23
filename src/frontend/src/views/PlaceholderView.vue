<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
const route=useRoute();const {t}=useI18n();const placeholder=computed(()=>route.meta.placeholder);const title=computed(()=>placeholder.value?.titleKey?t(String(placeholder.value.titleKey)):placeholder.value?.title??(route.meta.titleKey?t(String(route.meta.titleKey)):route.meta.title??t('placeholder.title')));const description=computed(()=>placeholder.value?.descriptionKey?t(String(placeholder.value.descriptionKey)):placeholder.value?.description??t('placeholder.description'));const endpoints=computed(()=>placeholder.value?.endpoints??[])
</script>
<template><el-card shadow="never"><el-empty :description="t('placeholder.developing',{title})"><p class="placeholder__desc">{{description}}</p><el-descriptions v-if="endpoints.length" :title="t('placeholder.endpoints')" :column="1" border class="placeholder__endpoints"><el-descriptions-item v-for="e in endpoints" :key="e" :label="e.split(' ')[0]"><code>{{e.split(' ').slice(1).join(' ')}}</code></el-descriptions-item></el-descriptions></el-empty></el-card></template>
<style scoped>.placeholder__desc{color:var(--el-text-color-secondary);max-width:560px;margin:0 auto 16px}.placeholder__endpoints{max-width:560px;margin:0 auto;text-align:left}</style>
