import { describe, expect, it } from 'vitest'

import { avatarImageUrl, siteImageUrl } from './image'

const SITE_URL = '/api/v1/files/users/abc/avatar/def'

describe('siteImageUrl', () => {
  it('站内文件按目标宽度就近向上取档', () => {
    expect(siteImageUrl(SITE_URL, 36)).toBe(`${SITE_URL}?w=96`)
    expect(siteImageUrl(SITE_URL, 96)).toBe(`${SITE_URL}?w=96`)
    expect(siteImageUrl(SITE_URL, 500)).toBe(`${SITE_URL}?w=640`)
    expect(siteImageUrl(SITE_URL, 1000)).toBe(`${SITE_URL}?w=1280`)
    expect(siteImageUrl(SITE_URL, 4000)).toBe(`${SITE_URL}?w=1280`)
  })

  it('外链、已带 query 与空值不改写', () => {
    expect(siteImageUrl('https://cdn.example.com/a.png', 96)).toBe('https://cdn.example.com/a.png')
    expect(siteImageUrl(`${SITE_URL}?w=192`, 96)).toBe(`${SITE_URL}?w=192`)
    expect(siteImageUrl(null, 96)).toBe('')
    expect(siteImageUrl('', 96)).toBe('')
  })
})

describe('avatarImageUrl', () => {
  it('按展示尺寸取 2x 档位', () => {
    expect(avatarImageUrl(SITE_URL, 36)).toBe(`${SITE_URL}?w=96`)
    expect(avatarImageUrl(SITE_URL, 120)).toBe(`${SITE_URL}?w=384`)
  })
})