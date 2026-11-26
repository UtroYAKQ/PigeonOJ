import type { ProblemLanguage } from '@/types'

/** 判题语言选项（首批三种，docs/architecture.md 领域约定）：详情页与验题面板共用 */
export const languageOptions: Array<{ label: string; value: ProblemLanguage }> = [
  { label: 'C++17', value: 'cpp17' },
  { label: 'Python 3.12', value: 'python3.12' },
  { label: 'Java 21', value: 'java21' },
]
