import { Progress } from '@/components/ui/progress'

interface ProcessingProgressProps {
  percent: number
  currentStep: string
  nextStep?: string
}

/** Evidence processing status (plan §13): "Processing 72% · Current step · Next". */
export function ProcessingProgress({ percent, currentStep, nextStep }: ProcessingProgressProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">Processing</span>
        <span className="font-mono tabular-nums">{percent}%</span>
      </div>
      <Progress value={percent} aria-label={`Processing ${percent}%`} />
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
        <dt className="text-muted-foreground">Current step</dt>
        <dd>{currentStep}</dd>
        {nextStep && (
          <>
            <dt className="text-muted-foreground">Next</dt>
            <dd>{nextStep}</dd>
          </>
        )}
      </dl>
    </div>
  )
}
