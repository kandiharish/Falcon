import type { ReactNode } from 'react'
import { OctagonX, RefreshCw, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: ReactNode
  action?: ReactNode
  className?: string
}

/** Never an unexplained blank page (plan §37): say what is missing and what to do next. */
export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-12 text-center',
        className,
      )}
    >
      <div className="flex size-11 items-center justify-center rounded-full bg-muted">
        <Icon aria-hidden className="size-5 text-muted-foreground" />
      </div>
      <div className="max-w-md space-y-1">
        <p className="font-medium">{title}</p>
        <div className="text-sm text-muted-foreground">{description}</div>
      </div>
      {action}
    </div>
  )
}

interface ErrorStateProps {
  title?: string
  description: string
  onRetry?: () => void
  retrying?: boolean
  className?: string
}

/** Human-readable error with a recovery action (plan §38). */
export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
  retrying,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-3 rounded-lg border border-destructive/25 bg-destructive/5 p-4',
        className,
      )}
    >
      <OctagonX aria-hidden className="mt-0.5 size-4 shrink-0 text-destructive" />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
          <RefreshCw className={cn(retrying && 'animate-spin')} />
          {retrying ? 'Retrying…' : 'Try again'}
        </Button>
      )}
    </div>
  )
}
