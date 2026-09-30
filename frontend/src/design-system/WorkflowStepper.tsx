import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { WorkflowStage } from '@/domain/types'
import { workflowStages } from './vocabulary'

/** Where the investigation is in the FALCON workflow (plan §44) — visible on every screen. */
export function WorkflowStepper({ stage, className }: { stage: WorkflowStage; className?: string }) {
  const currentIndex = workflowStages.findIndex((s) => s.stage === stage)
  return (
    <ol className={cn('flex items-center gap-1', className)} aria-label="Investigation workflow">
      {workflowStages.map((step, index) => {
        const state = index < currentIndex ? 'done' : index === currentIndex ? 'current' : 'upcoming'
        return (
          <li key={step.stage} className="flex items-center gap-1">
            {index > 0 && (
              <span
                aria-hidden
                className={cn('h-px w-3 lg:w-5', state === 'upcoming' ? 'bg-border' : 'bg-primary/50')}
              />
            )}
            <span
              aria-current={state === 'current' ? 'step' : undefined}
              className={cn(
                'inline-flex h-6 items-center gap-1 rounded-full px-2 text-xs whitespace-nowrap',
                state === 'done' && 'text-muted-foreground',
                state === 'current' && 'bg-primary/10 font-medium text-primary ring-1 ring-primary/30',
                state === 'upcoming' && 'text-muted-foreground/70',
              )}
            >
              {state === 'done' && <Check aria-hidden className="size-3" />}
              {step.label}
              {state === 'done' && <span className="sr-only"> (completed)</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
