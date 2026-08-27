import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { runProblemCode } from '@/api/judge'
import { message } from '@/utils/feedback'
import type { ProblemLanguage, SelfTestResult } from '@/types'

/**
 * 用户自测状态与会话（docs/contracts/judge.md「用户自测」）：
 * 输入 / 结果仅在当前页保留，不计分、不入提交记录；
 * 详情页与验题页工作台共用同一套控制台行为。
 */
export function useSelfTest(problemId: () => string) {
  const { t } = useI18n()
  const selfTestInput = ref('')
  const selfTesting = ref(false)
  const selfTestResult = ref<SelfTestResult | null>(null)

  async function runSelfTest(payload: { language: ProblemLanguage; code: string }) {
    if (selfTesting.value || !payload.code.trim()) return
    selfTesting.value = true
    try {
      selfTestResult.value = await runProblemCode({
        problem_id: problemId(),
        language: payload.language,
        code: payload.code,
        input: selfTestInput.value,
      })
    } catch (error) {
      // 后端错误消息已按 Accept-Language 本地化，直接透出；仅兜底网络层文案
      message.error(error instanceof Error ? error.message : t('problems.detail.selfTestFailed'))
    } finally {
      selfTesting.value = false
    }
  }

  return {
    selfTestInput,
    selfTesting,
    selfTestResult,
    runSelfTest,
  }
}
