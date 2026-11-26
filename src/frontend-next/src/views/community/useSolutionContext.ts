import { computed } from 'vue'
import { useRoute } from 'vue-router'

export function useSolutionContext() {
  const route = useRoute()
  const problemId = computed(() => String(route.params.problemId ?? route.params.id))
  /** 题目在当前业务上下文中的基路径（去掉 /solutions 及其后段） */
  const problemBase = computed(() => route.path.replace(/\/solutions(?:\/.*)?$/, ''))
  const solutionsBase = computed(() => `${problemBase.value}/solutions`)
  return { problemId, problemBase, solutionsBase }
}