import { describe, expect, it } from 'vitest'
import { createApp, defineComponent, h } from 'vue'

import { i18n } from '@/i18n'
import SearchFilterBar from './SearchFilterBar.vue'

/** 直接挂载组件并断言 n-input 渲染（naive 组件全局注册，此处仅验证 v-if 分支） */
describe('SearchFilterBar', () => {
  it('renders the keyword n-input by default', () => {
    const host = defineComponent({
      render: () => h(SearchFilterBar, { keyword: '', placeholder: '搜索题目名称' }),
    })
    const root = document.createElement('div')
    document.body.appendChild(root)
    createApp(host).use(i18n).mount(root)
    expect(root.querySelector('.search-filter-bar')).not.toBeNull()
    expect(root.querySelector('n-input')).not.toBeNull()
    expect(root.innerHTML).toContain('搜索题目名称')
  })

  it('hides the keyword n-input with showSearch=false', () => {
    const host = defineComponent({
      render: () => h(SearchFilterBar, { showSearch: false }),
    })
    const root = document.createElement('div')
    document.body.appendChild(root)
    createApp(host).use(i18n).mount(root)
    expect(root.querySelector('n-input')).toBeNull()
  })
})
