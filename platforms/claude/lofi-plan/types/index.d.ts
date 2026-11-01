export type PlanPhase = 'explore' | 'ask' | 'design' | 'review' | 'build'

export type PlanStep = {
  id: string
  text: string
  active: string
  status: 'pending' | 'in_progress' | 'completed'
}

export type Plan = {
  // null while no plan is being formed or worked through.
  phase: PlanPhase | null
  steps: PlanStep[]
  updatedAt: number
}

declare module 'claude-code' {
  interface PluginState {
    'lofi-plan': { plan: Shaped<Plan> }
  }
}
