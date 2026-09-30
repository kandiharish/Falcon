import { cn } from '@/lib/utils'
import { toneFillClass, toneTextClass } from './tones'
import { confidenceLevel, confidenceTerms } from './vocabulary'

interface ConfidenceIndicatorProps {
  score: number // 0..1
  className?: string
}

/** Bars + word + number: readable without colour (plan §36). */
export function ConfidenceIndicator({ score, className }: ConfidenceIndicatorProps) {
  const level = confidenceLevel(score)
  const term = confidenceTerms[level]
  return (
    <span
      className={cn('inline-flex items-center gap-1.5 text-xs', className)}
      aria-label={`Confidence ${term.label}, ${score.toFixed(2)}`}
    >
      <span aria-hidden className="flex items-end gap-0.5">
        {[1, 2, 3].map((bar) => (
          <span
            key={bar}
            className={cn(
              'w-1 rounded-sm',
              bar <= term.bars ? toneFillClass[term.tone] : 'bg-muted-foreground/25',
            )}
            style={{ height: 4 + bar * 3 }}
          />
        ))}
      </span>
      <span className={cn('font-medium', toneTextClass[term.tone])}>{term.label}</span>
      <span className="font-mono text-muted-foreground tabular-nums">{score.toFixed(2)}</span>
    </span>
  )
}
