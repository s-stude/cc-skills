import { expect, test } from 'claude-code/testing'

const MESSAGE =
  'Context is at 80%+. Hand off to a fresh Claude Code session with the context-handoff:handoff-to-new-session skill.'

const measure = (percent: number) => ({
  context: { tokens: percent * 2000, window: 200_000, percent },
  rateLimits: [],
  changed: ['context' as const],
})

test('sends the handoff prompt once at 80%, re-arms below it', async ($, on) => {
  const sent: { text: string; asUser?: true }[] = []
  on('session.measure', (_, e) => ({ changed: e.changed }))
  on('prompt.submit', (_, e) => {
    sent.push({ text: e.text, asUser: e.origin.kind === 'plugin' ? e.origin.asUser : undefined })
    return { text: e.text }
  })

  await $.session.measure(measure(50))
  expect(sent.length).toBe(0)

  await $.session.measure(measure(81))
  await $.session.measure(measure(90))
  expect(sent.length).toBe(1)
  expect(sent[0].text).toBe(MESSAGE)
  expect(sent[0].asUser).toBe(true)

  await $.session.measure(measure(30))
  await $.session.measure(measure(85))
  expect(sent.length).toBe(2)
})
