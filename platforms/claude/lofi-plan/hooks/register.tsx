import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Plan, PlanPhase, PlanStep } from '../types'

// The lo-fi palette, shared with lofi-usage: muted tones that read on light and dark themes.
const INK = { sage: '#8fa88a', lilac: '#9d8ec7' }

const PHASES: { id: PlanPhase; label: string }[] = [
  { id: 'explore', label: 'изучение' },
  { id: 'ask', label: 'вопросы' },
  { id: 'design', label: 'проект' },
  { id: 'review', label: 'согласование' },
  { id: 'build', label: 'работа' },
]

const FRESH: Plan = { phase: null, steps: [], updatedAt: 0 }
// Change the tag when Plan's fields change: it declines what an earlier version stored.
const plan = atom({ plugin: 'lofi-plan', key: 'plan' } as const, FRESH, { shape: 'plan-4' })

// Tools that only look around: what the explore phase is made of.
const LOOKING = new Set(['Read', 'Grep', 'Glob', 'LSP', 'WebFetch', 'WebSearch', 'Bash', 'ToolSearch'])

// A finished plan keeps its bar under the prompt this long, then the line is the engine's again.
const FINISHED_FOR_MS = 120_000

// Whether the hint line has been seen naming plan mode: only then does its absence mean the mode is off.
let hasSeenPlanHint = false

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // The "updated 12s ago" figure ages while nothing happens.
    $.clock.every(5_000, () => $.ui.invalidate('ui.render'))

    return next(e)
  })

  // Plan mode switched with shift+tab reaches the mod only through the prompt's mode.
  // The mod only watches, so a failure here lets the prompt through.
  on('classic.UserPromptSubmit', async ($, e, next) => {
    if (e.agent_id === undefined && e.permission_mode !== undefined) {
      const isPlanMode = e.permission_mode === 'plan'
      const isPlanning = isForming(await read($, plan))

      if (isPlanMode && !isPlanning) {
        await begin($)
      }

      // A prompt sent outside plan mode drops a plan that was still forming.
      if (!isPlanMode && isPlanning) {
        await update($, plan, () => FRESH)
      }
    }

    return next(e)
  }).catch(($, e, next) => next(e))

  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear') {
      await update($, plan, () => FRESH)
    }

    return next(e)
  })

  // Each call moves the plan along; a failure here never refuses the call.
  on('tool.call', async ($, e, next) => {
    const isMain = e.agentId === undefined

    if (isMain && e.tool === 'EnterPlanMode') {
      await begin($)

      return next(e)
    }

    if (isMain && e.tool === 'ExitPlanMode') {
      await record($, 'review')
      const ran = await next(e)
      const isApproved = ran.deny === undefined && ran.isError !== true

      await record($, isApproved ? 'build' : 'design')

      return ran
    }

    if (isMain && e.tool === 'TodoWrite') {
      const steps: PlanStep[] = e.todos.map((todo, i) => ({
        id: `todo-${i}`,
        text: todo.content,
        active: todo.activeForm,
        status: todo.status,
      }))
      await touch($, p => ({ ...working(p), steps }))

      return next(e)
    }

    if (isMain && e.tool === 'TaskCreate') {
      const ran = await next(e)
      const id = (ran.result as { task?: { id?: string } } | undefined)?.task?.id

      if (id !== undefined) {
        const step: PlanStep = { id, text: e.subject, active: e.activeForm ?? e.subject, status: 'pending' }
        await touch($, p => {
          const isStale = p.steps.length > 0 && p.steps.every(one => one.status === 'completed')

          return { ...working(p), steps: [...(isStale ? [] : p.steps), step] }
        })
      }

      return ran
    }

    if (isMain && e.tool === 'TaskUpdate') {
      const ran = await next(e)

      if (ran.deny === undefined && ran.isError !== true) {
        await touch($, p => ({
          ...p,
          steps:
            e.status === 'deleted'
              ? p.steps.filter(one => one.id !== e.taskId)
              : p.steps.map(one =>
                  one.id === e.taskId
                    ? {
                        ...one,
                        text: e.subject ?? one.text,
                        active: e.activeForm ?? one.active,
                        status: e.status ?? one.status,
                      }
                    : one,
                ),
        }))
      }

      return ran
    }

    // While the plan is forming, every call (a subagent's too) says which phase it is in.
    if (!isForming(await read($, plan))) {
      return next(e)
    }

    const phase = phaseOf(String(e.tool), e as unknown as Record<string, unknown>)

    if (phase !== null) {
      await record($, phase)
    }

    return next(e)
  }).catch(($, e, next) => next(e))

  // Under the prompt: one short line of where the plan stands, the engine's own hint kept at its right.
  on('ui.render', { component: 'PromptHint' }, async ($, e, next) => {
    const p = await read($, plan)
    const now = await $.clock.now()
    const engine = await next(e)
    const isPlanHint = /plan mode/i.test(e.props.hint)
    hasSeenPlanHint ||= isPlanHint
    // Switched out of plan mode while idle: the plan in the making is no longer on screen.
    const hasLeft = isForming(p) && hasSeenPlanHint && !isPlanHint && !e.props.isWorking

    if (p.phase === null || hasLeft || (isFinished(p) && now - p.updatedAt > FINISHED_FOR_MS)) {
      return engine
    }

    const { Box, Text } = $.ui.resolve(e)
    const done = p.steps.filter(step => step.status === 'completed').length
    const total = p.steps.length
    const stage = PHASES.findIndex(one => one.id === p.phase) + 1
    const isBuilding = p.phase === 'build' && total > 0
    const share = isBuilding ? done / total : stage / PHASES.length
    const cells = 10
    const full = Math.round(share * cells)
    const finished = isFinished(p)
    const tone = finished ? INK.sage : INK.lilac
    const label = finished ? 'готово' : (PHASES[stage - 1]?.label ?? '')
    const count = isBuilding ? `${done}/${total}` : `этап ${stage}/${PHASES.length}`
    const doing = isBuilding ? p.steps.find(step => step.status === 'in_progress')?.active : undefined
    const isNarrow = (e.viewport?.columns ?? 120) < 90

    const bar = (
      <Box flexShrink={1}>
        <Text wrap="truncate-end">
          <Text color={tone}>{finished ? '●' : '◉'} </Text>
          <Text color={tone}>{label} </Text>
          <Text color={tone}>{'━'.repeat(full)}</Text>
          <Text dimColor>{'─'.repeat(cells - full)}</Text>
          <Text dimColor>
            {' '}
            {count} · ↻ {ago(now - p.updatedAt)}
            {doing !== undefined && ` · ${doing}`}
          </Text>
        </Text>
      </Box>
    )

    return isNarrow ? (
      <Box flexDirection="column">
        {bar}
        {engine}
      </Box>
    ) : (
      <Box flexDirection="row" justifyContent="space-between">
        {bar}
        <Box flexShrink={0} marginLeft={2}>
          {engine}
        </Box>
      </Box>
    )
  })
}

async function begin($: EngineInterface) {
  const now = await $.clock.now()
  await update($, plan, () => ({ ...FRESH, phase: 'explore', updatedAt: now }))
}

async function touch($: EngineInterface, change: (p: Plan) => Plan) {
  const now = await $.clock.now()
  await update($, plan, p => ({ ...change(p), updatedAt: now }))
}

async function record($: EngineInterface, phase: PlanPhase) {
  await touch($, p => ({ ...p, phase }))
}

function isForming(p: Plan): boolean {
  return p.phase !== null && p.phase !== 'build'
}

function isFinished(p: Plan): boolean {
  return p.phase === 'build' && p.steps.length > 0 && p.steps.every(step => step.status === 'completed')
}

// Steps outside plan mode still make a plan: one already at work.
function working(p: Plan): Plan {
  return p.phase === null ? { ...p, phase: 'build' } : p
}

function phaseOf(tool: string, input: Record<string, unknown>): PlanPhase | null {
  if (tool === 'AskUserQuestion') return 'ask'
  if (tool === 'Write' || tool === 'Edit') return 'design'
  if (tool === 'Agent') return input.subagent_type === 'Plan' ? 'design' : 'explore'
  if (LOOKING.has(tool)) return 'explore'

  return null
}

function ago(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000))

  if (seconds < 10) return 'сейчас'
  if (seconds < 60) return `${seconds}с`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}м`

  return `${Math.floor(seconds / 3600)}ч`
}
