import { describe, expect, it } from 'vitest'

import { problemSetVisibilityKey, problemSetVisibilityTagType } from './visibilityLabel'

describe('problemSetVisibilityKey', () => {
  it('maps known visibilities to nested i18n keys', () => {
    expect(problemSetVisibilityKey('public')).toBe('problemSets.visibility.public')
    expect(problemSetVisibilityKey('private')).toBe('problemSets.visibility.private')
    expect(problemSetVisibilityKey('team_visible')).toBe('problemSets.visibility.team_visible')
    expect(problemSetVisibilityKey('admin_visible')).toBe('problemSets.visibility.admin_visible')
  })

  it('falls back to private for unknown values', () => {
    expect(problemSetVisibilityKey('team')).toBe('problemSets.visibility.private')
    expect(problemSetVisibilityKey('')).toBe('problemSets.visibility.private')
  })
})

describe('problemSetVisibilityTagType', () => {
  it('uses info for public / team-visible, warning for admin-visible, error otherwise', () => {
    expect(problemSetVisibilityTagType('public')).toBe('info')
    expect(problemSetVisibilityTagType('team_visible')).toBe('info')
    expect(problemSetVisibilityTagType('admin_visible')).toBe('warning')
    expect(problemSetVisibilityTagType('private')).toBe('error')
  })
})
