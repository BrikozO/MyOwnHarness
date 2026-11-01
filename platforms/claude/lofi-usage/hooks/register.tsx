import { atom, read, update } from 'claude-code'
import type { Register, SessionContextUsage, SessionRateLimit } from 'claude-code'

import type { Meter, Usage } from '../types'

// The lo-fi palette, shared with lofi-plan: muted tones that read on light and dark themes.
const INK = { sage: '#8fa88a', sand: '#c4a46e', rose: '#c48282', lilac: '#9d8ec7' }

const EMPTY: Usage = { context: null, limits: [] }
// Change the tag when Usage's fields change: it declines what an earlier version stored.
const usage = atom({ plugin: 'lofi-usage', key: 'usage' } as const, EMPTY, { shape: 'usage-2' })

const LABELS: Record<string, string> = { five_hour: '5h', seven_day: '7d', spend_limit: 'spend' }

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    const now = await $.session.usage()
    await update($, usage, () => snapshot(now.context, now.rateLimits))
    // The reset countdowns age while the session sits idle.
    $.clock.every(60_000, () => $.ui.invalidate('ui.render'))

    return started
  })

  on('session.measure', async ($, e, next) => {
    await update($, usage, () => snapshot(e.context, e.rateLimits))

    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const stored = await read($, usage)
    // After a /clear the new session starts with empty state and no session.start: ask the engine.
    const now = isEmpty(stored)
      ? await $.session.usage().then(fresh => snapshot(fresh.context, fresh.rateLimits))
      : stored

    if (e.props.hasSurvey || isEmpty(now)) {
      return next(e)
    }

    const { Box, Text } = $.ui.resolve(e)
    const clock = await $.clock.now()
    const isWide = e.props.bodyColumns >= 76
    const cells = isWide ? 10 : 6
    const readings: Reading[] = []

    if (now.context !== null) {
      const { tokens, window, percent } = now.context
      readings.push({ label: 'ctx', percent, note: isWide ? `${short(tokens)}/${short(window)}` : '' })
    }

    for (const limit of now.limits) {
      const left = until(limit.resetsAt, clock)
      const label = LABELS[limit.kind] ?? limit.kind.replace(/_/g, ' ')
      readings.push({ label, percent: limit.percent, note: left && `↺ ${left}` })
    }

    // One reading: a dim label, a bar tinted by how full it is, the percent, a dim note.
    return (
      <Box flexDirection="row" paddingX={1}>
        {readings.map((reading, i) => {
          const full = Math.round((Math.min(100, Math.max(0, reading.percent)) / 100) * cells)
          const tone = toneOf(reading.percent)

          return (
            <Text>
              {i > 0 && <Text dimColor>{'  ·  '}</Text>}
              <Text dimColor>{reading.label} </Text>
              <Text color={tone}>{'━'.repeat(full)}</Text>
              <Text dimColor>{'─'.repeat(cells - full)}</Text>
              <Text color={tone}> {Math.round(reading.percent)}%</Text>
              {reading.note !== '' && <Text dimColor> {reading.note}</Text>}
            </Text>
          )
        })}
      </Box>
    )
  })
}

type Reading = { label: string; percent: number; note: string }

function toneOf(percent: number): string {
  return percent < 60 ? INK.sage : percent < 85 ? INK.sand : INK.rose
}

function isEmpty(usage: Usage): boolean {
  return usage.context === null && usage.limits.length === 0
}

function snapshot(context: SessionContextUsage, limits: readonly SessionRateLimit[]): Usage {
  const tokens = context.tokens ?? 0
  const percent = context.window > 0 ? Math.round(context.percent ?? (tokens / context.window) * 100) : 0
  const meters: Meter[] = limits.map(limit => ({ kind: limit.kind, percent: limit.percentUsed, resetsAt: limit.resetsAt }))

  return {
    context: context.window > 0 ? { tokens, window: context.window, percent } : null,
    limits: meters,
  }
}

function until(resetsAt: string | undefined, now: number): string {
  const ms = resetsAt === undefined ? NaN : Date.parse(resetsAt) - now

  if (!(ms > 0)) {
    return ''
  }

  const minutes = Math.ceil(ms / 60_000)

  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h${String(minutes % 60).padStart(2, '0')}m`

  return `${Math.floor(hours / 24)}d${hours % 24}h`
}

function short(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`

  return String(n)
}
