import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

const THRESHOLD = 80
const MESSAGE =
  'Context is at 80%+. Hand off to a fresh Claude Code session with the context-handoff:handoff-to-new-session skill.'

// Kept in $.state so a reload of the mod doesn't send the prompt again.
const fired = atom({ plugin: 'context-handoff', key: 'fired' } as const, false)

export const register: Register = on => {
  on('session.measure', async ($, e, next) => {
    const percent = e.context.percent
    if (percent === undefined || !e.changed.includes('context')) return next(e)

    const hasFired = await read($, fired)

    if (percent >= THRESHOLD && !hasFired) {
      await update($, fired, () => true)
      // Not awaited: submit waits for the session to go idle.
      void $.prompt.submit({ text: MESSAGE, asUser: true })
    } else if (percent < THRESHOLD && hasFired) {
      // Re-arm after /compact brings the context back down.
      await update($, fired, () => false)
    }

    return next(e)
  })
}
