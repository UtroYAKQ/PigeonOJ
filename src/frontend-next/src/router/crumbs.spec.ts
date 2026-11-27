import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { describe, expect, it } from 'vitest'

import { buildCrumbs } from './crumbs'

function fakeRoute(
  matched: Array<{ path: string; meta?: Record<string, unknown> }>,
  params: Record<string, string>,
): RouteLocationNormalizedLoaded {
  return { matched, params } as unknown as RouteLocationNormalizedLoaded
}

describe('buildCrumbs', () => {
  it('代码编辑面包屑的详情项链接到解析后的详情路径', () => {
    const route = fakeRoute(
      [
        { path: '/codes', meta: { titleKey: 'nav.codePlaza' } },
        { path: ':id', meta: {} },
        {
          path: 'edit',
          meta: {
            titleKey: 'codes.editTitle',
            breadcrumbParent: [
              {
                titleKey: 'codes.detailTitle',
                path: (current: RouteLocationNormalizedLoaded) =>
                  `/codes/${current.params.id}`,
              },
              { titleKey: 'nav.codePlaza', path: '/codes' },
            ],
          },
        },
      ],
      { id: 'share-123' },
    )

    expect(buildCrumbs(route, (key) => key)).toEqual([
      { label: 'nav.codePlaza', to: '/codes' },
      { label: 'codes.detailTitle', to: '/codes/share-123' },
      { label: 'codes.editTitle', to: undefined },
    ])
  })
})
