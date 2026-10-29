import { expect, mock, test } from 'claude-code/testing'

const BAND = {
  plugin: 'lofi-usage',
  component: 'AbovePrompt',
  requestId: 'band',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 10,
    bodyColumns: 120,
    scroll: { offset: 0, bodyRows: 10 },
    view: {},
  },
} as const

const USAGE = {
  startedAt: 0,
  context: { tokens: 68_000, window: 200_000, percent: 34 },
  rateLimits: [
    { kind: 'five_hour', percentUsed: 22, resetsAt: '2026-10-27T12:14:00Z' },
    { kind: 'seven_day', percentUsed: 91, resetsAt: '2026-10-30T13:00:00Z' },
  ],
  cost: { usd: 1.24 },
}

test('the band reads context and both limits with their resets, and no cost', async ($, on) => {
  mock.clock(on, { now: Date.parse('2026-10-27T10:00:00Z') })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.usage', () => ({ value: USAGE }))

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })

    expect((await ui.find({ type: 'Text', text: /^ctx/ }))?.text).toBe('ctx ━━━─────── 34% 68k/200k')
    expect((await ui.find({ type: 'Text', text: /5h/ }))?.text).toBe('  ·  5h ━━──────── 22% ↺ 2h14m')
    expect((await ui.find({ type: 'Text', text: /7d/ }))?.text).toBe('  ·  7d ━━━━━━━━━─ 91% ↺ 3d3h')
    expect(await ui.find({ type: 'Text', text: /\$/ })).toBeUndefined()
    await ui.unmount()
  }
})

test('a narrow band drops the token counts', async ($, on) => {
  mock.clock(on, { now: Date.parse('2026-10-27T10:00:00Z') })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.usage', () => ({ value: USAGE }))

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal', props: { ...BAND.props, bodyColumns: 60 } })

  expect((await ui.find({ type: 'Text', text: /^ctx/ }))?.text).toBe('ctx ━━──── 34%')
  expect(await ui.find({ type: 'Text', text: /68k/ })).toBeUndefined()
  await ui.unmount()
})

test('after a /clear, with no session.start, the band reads the engine directly', async ($, on) => {
  mock.clock(on, { now: Date.parse('2026-10-27T10:00:00Z') })
  on('session.usage', () => ({ value: { ...USAGE, context: { window: 200_000 } } }))

  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })

  expect((await ui.find({ type: 'Text', text: /^ctx/ }))?.text).toBe('ctx ────────── 0% 0/200k')
  expect((await ui.find({ type: 'Text', text: /5h/ }))?.text).toBe('  ·  5h ━━──────── 22% ↺ 2h14m')
  await ui.unmount()
})

test('with no reading yet the band is left to the engine', async ($, on) => {
  on('session.usage', () => ({ value: { startedAt: 0, context: { window: 0 }, rateLimits: [] } }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine</Text>
  })

  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })

  expect((await ui.find({ type: 'Text' }))?.text).toBe('engine')
  await ui.unmount()
})
