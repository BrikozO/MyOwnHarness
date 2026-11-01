import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const HINT = {
  plugin: 'lofi-plan',
  component: 'PromptHint',
  props: { isDraft: false, isWorking: true, hint: '? for shortcuts' },
  viewport: { columns: 140, rows: 40, isFullscreen: true },
} as const

const IDLE_IN_PLAN = { ...HINT, props: { isDraft: false, isWorking: false, hint: '⏸ plan mode on (shift+tab to cycle)' } }
const IDLE_OUT_OF_PLAN = { ...HINT, props: { isDraft: false, isWorking: false, hint: '? for shortcuts' } }

const PLAN_FILE = '/Users/me/.claude/plans/quiet-pelican.md'
const PLAN_TEXT = '# Redis DAO для пользователей\n\n## Context\ntext\n## Шаги\n### модели\n### dao\n## Проверка\n'

// Nothing sits beneath the plugin: each hook here stands for the engine.
function engine(on: On, opened: string[] = []) {
  on('ui.open', (_, e) => {
    opened.push(e.id)

    return { value: { isPlaced: true } }
  })
  on('ui.panes', () => ({ value: [] }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('classic.UserPromptSubmit', () => ({}))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>? for shortcuts</Text>
  })
  on('tool.call', (_, e) => {
    if (e.tool === 'ExitPlanMode') return { result: { plan: PLAN_TEXT, isAgent: false } }
    if (e.tool === 'TaskCreate') return { result: { task: { id: e.subject === 'модели' ? '1' : '2', subject: e.subject } } }

    return { result: {} }
  })
}

test('the line under the prompt follows a plan as it forms, with no commands and no pane', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000_000 })
  const opened: string[] = []
  engine(on, opened)

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'EnterPlanMode' })
  await $.tool.call({ tool: 'Bash', command: 'git log --oneline | head' })

  const exploring = await $.ui.mount({ ...HINT, surface: 'terminal' })
  expect((await exploring.find({ type: 'Text', text: /^◉/ }))?.text).toBe('◉ изучение ━━──────── этап 1/5 · ↻ сейчас')
  expect(await exploring.find({ type: 'Text', text: /git log/ })).toBeUndefined()
  await exploring.unmount()

  await $.tool.call({ tool: 'Grep', pattern: 'UserDAO' })
  await $.tool.call({
    tool: 'AskUserQuestion',
    questions: [{ question: 'Где хранить сессии?', header: 'Сессии', multiSelect: false, options: [] }],
  })
  await $.tool.call({ tool: 'Write', file_path: PLAN_FILE, content: PLAN_TEXT })
  await clock.advance(15_000)

  for (const surface of ['terminal', 'desktop'] as const) {
    const hint = await $.ui.mount({ ...HINT, surface })
    expect((await hint.find({ type: 'Text', text: /^◉/ }))?.text).toBe('◉ проект ━━━━━━──── этап 3/5 · ↻ 15с')
    expect((await hint.find({ type: 'Text', text: /shortcuts/ }))?.text).toBe('? for shortcuts')
    await hint.unmount()
  }

  expect(opened).toEqual([])
})

test('a prompt sent in plan mode starts the line', async ($, on) => {
  mock.clock(on, { now: 1_000_000 })
  engine(on)

  await $.classic.UserPromptSubmit({ prompt: 'составь план', permission_mode: 'plan' })

  const hint = await $.ui.mount({ ...IDLE_IN_PLAN, surface: 'terminal' })
  expect((await hint.find({ type: 'Text', text: /^◉/ }))?.text).toBe('◉ изучение ━━──────── этап 1/5 · ↻ сейчас')
  await hint.unmount()
})

test('switching out of plan mode hides the line, and the next prompt drops the plan', async ($, on) => {
  mock.clock(on, { now: 1_000_000 })
  engine(on)

  await $.tool.call({ tool: 'EnterPlanMode' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/domain/models.py' })

  const inPlan = await $.ui.mount({ ...IDLE_IN_PLAN, surface: 'terminal' })
  expect((await inPlan.find({ type: 'Text', text: /^◉/ }))?.text).toBe('◉ изучение ━━──────── этап 1/5 · ↻ сейчас')
  await inPlan.unmount()

  const outOfPlan = await $.ui.mount({ ...IDLE_OUT_OF_PLAN, surface: 'terminal' })
  expect(await outOfPlan.find({ type: 'Text', text: /изучение/ })).toBeUndefined()
  expect((await outOfPlan.find({ type: 'Text' }))?.text).toBe('? for shortcuts')
  await outOfPlan.unmount()

  await $.classic.UserPromptSubmit({ prompt: 'просто вопрос', permission_mode: 'default' })

  const backInPlan = await $.ui.mount({ ...IDLE_IN_PLAN, surface: 'terminal' })
  expect(await backInPlan.find({ type: 'Text', text: /изучение/ })).toBeUndefined()
  await backInPlan.unmount()
})

test('after approval the line counts steps, then gives the row back once done', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000_000 })
  engine(on)

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'EnterPlanMode' })
  await $.tool.call({ tool: 'ExitPlanMode' })
  await $.tool.call({ tool: 'TaskCreate', subject: 'модели', description: 'd' })
  await $.tool.call({ tool: 'TaskCreate', subject: 'dao', description: 'd', activeForm: 'пишу dao' })
  await $.tool.call({ tool: 'TaskUpdate', taskId: '1', status: 'completed' })
  await $.tool.call({ tool: 'TaskUpdate', taskId: '2', status: 'in_progress' })

  const working = await $.ui.mount({ ...HINT, surface: 'terminal' })
  expect((await working.find({ type: 'Text', text: /^◉/ }))?.text).toBe('◉ работа ━━━━━───── 1/2 · ↻ сейчас · пишу dao')
  await working.unmount()

  // Out of plan mode the steps still count: switching modes hides only a plan still forming.
  const idle = await $.ui.mount({ ...IDLE_OUT_OF_PLAN, surface: 'terminal' })
  expect((await idle.find({ type: 'Text', text: /^◉/ }))?.text).toBe('◉ работа ━━━━━───── 1/2 · ↻ сейчас · пишу dao')
  await idle.unmount()

  await $.tool.call({ tool: 'TaskUpdate', taskId: '2', status: 'completed' })
  const done = await $.ui.mount({ ...HINT, surface: 'terminal' })
  expect((await done.find({ type: 'Text', text: /^●/ }))?.text).toBe('● готово ━━━━━━━━━━ 2/2 · ↻ сейчас')
  await done.unmount()

  await clock.advance(121_000)
  const later = await $.ui.mount({ ...HINT, surface: 'terminal' })
  expect(await later.find({ type: 'Text', text: /готово/ })).toBeUndefined()
  expect((await later.find({ type: 'Text', text: /shortcuts/ }))?.text).toBe('? for shortcuts')
  await later.unmount()
})

test('with no plan the hint line is the engine’s', async ($, on) => {
  engine(on)

  const hint = await $.ui.mount({ ...HINT, surface: 'terminal' })
  expect((await hint.find({ type: 'Text' }))?.text).toBe('? for shortcuts')
  await hint.unmount()
})

test('a plan the previous version stored is declined', async ($, on) => {
  engine(on)
  on('state.get', () => ({
    value: {
      value: { shape: 'plan-3', value: { phase: 'explore', last: 'читаю models.py', steps: [], updatedAt: 0 } },
      version: 1,
    },
  }))

  const hint = await $.ui.mount({ ...HINT, surface: 'terminal' })
  expect((await hint.find({ type: 'Text' }))?.text).toBe('? for shortcuts')
  await hint.unmount()
})
