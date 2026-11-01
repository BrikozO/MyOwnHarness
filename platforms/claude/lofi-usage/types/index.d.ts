export type Meter = { kind: string; percent: number; resetsAt?: string }

export type Usage = {
  context: { tokens: number; window: number; percent: number } | null
  limits: Meter[]
}

declare module 'claude-code' {
  interface PluginState {
    'lofi-usage': { usage: Shaped<Usage> }
  }
}
