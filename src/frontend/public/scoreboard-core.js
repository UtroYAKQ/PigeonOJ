// Replay arithmetic only. Shared spectators receive already projected rows.
export function compareText(a, b) {
  const left = [...String(a)],
    right = [...String(b)]
  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    const delta = left[i].codePointAt(0) - right[i].codePointAt(0)
    if (delta) return delta
  }
  return left.length - right.length
}

export function rankRows(rows, rule) {
  for (const row of rows) {
    row.solved = row.cells.filter((c) => c.accepted).length
    row.total_penalty = row.cells.reduce((n, c) => n + c.penalty, 0)
    row.total_score = row.cells.reduce((n, c) => n + c.score, 0)
  }
  rows.sort(
    (a, b) =>
      (rule === 'ACM'
        ? b.solved - a.solved || a.total_penalty - b.total_penalty
        : b.total_score - a.total_score || b.solved - a.solved) ||
      compareText(a.nickname, b.nickname) ||
      compareText(a.user_id, b.user_id),
  )
  rows.forEach((row, i) => {
    row.rank = i + 1
  })
  return rows
}

export function replayRows(data, cursor) {
  const rows = structuredClone(data.base_rows)
  const index = new Map(rows.map((row) => [row.user_id, row]))
  for (const step of data.steps.slice(0, cursor)) {
    const row = index.get(step.user_id)
    if (!row || !step.cell) continue
    const i = row.cells.findIndex((c) => c.problem_id === step.problem_id)
    if (i !== -1) row.cells[i] = structuredClone(step.cell)
  }
  return rankRows(rows, data.rule_type)
}

export function escapeHtml(value) {
  return String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  )
}

export function cellMarkup(cell, rule, first = false) {
  if (!cell) return '<span class="cell idle">·</span>'
  const accepted =
    cell.accepted || (rule === 'IOI' && cell.problem_score > 0 && cell.score >= cell.problem_score)
  const pending = cell.pending > 0
  const cls = accepted ? 'ac' : cell.score > 0 ? 'part' : cell.attempts ? 'try' : 'idle'
  const main =
    rule === 'ACM'
      ? cell.accepted
        ? `+${cell.attempts || ''}`
        : cell.attempts
          ? `−${cell.attempts}`
          : '·'
      : cell.score
  return `<span class="cell ${cls}${pending ? ' pending' : ''}${first ? ' first' : ''}">${main}${pending ? `<b class="unknown">?${cell.pending}</b>` : ''}${cell.accepted && rule === 'ACM' ? `<small>${cell.penalty} min</small>` : ''}</span>`
}
