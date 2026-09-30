import { cn } from '@/lib/utils'
import type {
  EvidenceStatus,
  InvestigationStatus,
  Priority,
  ReviewStatus,
  TaskStatus,
} from '@/domain/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { toneBadgeClass, toneFillClass } from './tones'
import {
  assertionTerms,
  evidenceStatusTerms,
  investigationStatusTerms,
  priorityTerms,
  reviewStatusTerms,
  taskStatusTerms,
  type Term,
} from './vocabulary'
import type { AssertionKind } from '@/domain/types'

const badgeBase =
  'inline-flex h-5.5 shrink-0 items-center gap-1 rounded-md border px-1.5 text-xs font-medium whitespace-nowrap'

/** Icon + text + tone. Never colour alone (plan §36). */
function TermBadge({ term, className }: { term: Term; className?: string }) {
  const Icon = term.icon
  return (
    <span className={cn(badgeBase, toneBadgeClass[term.tone], className)}>
      <Icon aria-hidden className="size-3.5" />
      {term.label}
    </span>
  )
}

type StatusBadgeProps =
  | { kind: 'investigation'; status: InvestigationStatus }
  | { kind: 'evidence'; status: EvidenceStatus }
  | { kind: 'review'; status: ReviewStatus }
  | { kind: 'task'; status: TaskStatus }

export function StatusBadge(props: StatusBadgeProps & { className?: string }) {
  const term =
    props.kind === 'investigation'
      ? investigationStatusTerms[props.status]
      : props.kind === 'evidence'
        ? evidenceStatusTerms[props.status]
        : props.kind === 'review'
          ? reviewStatusTerms[props.status]
          : taskStatusTerms[props.status]
  return <TermBadge term={term} className={props.className} />
}

export function PriorityBadge({ priority, className }: { priority: Priority; className?: string }) {
  const term = priorityTerms[priority]
  return (
    <span
      className={cn(badgeBase, toneBadgeClass[term.tone], className)}
      aria-label={`Priority: ${term.label}`}
    >
      <span aria-hidden className="flex items-end gap-px">
        {[1, 2, 3, 4].map((step) => (
          <span
            key={step}
            className={cn(
              'w-0.5 rounded-full',
              step <= term.level ? toneFillClass[term.tone] : 'bg-current opacity-20',
            )}
            style={{ height: 3 + step * 2 }}
          />
        ))}
      </span>
      {term.label}
    </span>
  )
}

/** Provenance label with an explanation on hover/focus. */
export function AssertionLabel({ kind, className }: { kind: AssertionKind; className?: string }) {
  const term = assertionTerms[kind]
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className={cn('rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring', className)}>
          <TermBadge term={term} className="uppercase tracking-wide text-[0.675rem]" />
        </span>
      </TooltipTrigger>
      <TooltipContent>{term.description}</TooltipContent>
    </Tooltip>
  )
}
