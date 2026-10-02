/**
 * Building blocks for correlations: a pair of evidence, its level, and the factors behind it.
 * A correlation is a POTENTIAL relationship: always shown with its reasons, never as a verdict.
 */
import { Link } from 'react-router'
import { ArrowLeftRight, History } from 'lucide-react'
import type { Correlation, CorrelationFactor, CorrelationLevel } from '@/domain/types'
import { StatusBadge } from '@/design-system/badges'
import { toneBadgeClass, toneFillClass } from '@/design-system/tones'
import { evidenceTypeTerms } from '@/design-system/vocabulary'
import type { EvidenceType } from '@/domain/types'
import { cn } from '@/lib/utils'
import { EvidenceChip } from '@/features/extraction/components'
import { factorTerms, levelTerms } from './terms'

/** Strength of the relationship: bars + word + score, readable without colour. */
export function LevelBadge({ level, score, className }: { level: CorrelationLevel; score: number; className?: string }) {
  const term = levelTerms[level]
  return (
    <span
      className={cn('inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-xs font-medium', toneBadgeClass[term.tone], className)}
      aria-label={`${term.label} correlation, score ${score.toFixed(2)}`}
    >
      <span aria-hidden className="flex items-end gap-0.5">
        {[1, 2, 3].map((bar) => (
          <span
            key={bar}
            className={cn('w-1 rounded-sm', bar <= term.bars ? toneFillClass[term.tone] : 'bg-current/20')}
            style={{ height: 4 + bar * 3 }}
          />
        ))}
      </span>
      {term.label}
      <span className="font-mono tabular-nums opacity-80">{score.toFixed(2)}</span>
    </span>
  )
}

export function FactorChip({ factor }: { factor: CorrelationFactor }) {
  const term = factorTerms[factor.kind]
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border bg-card px-1.5 py-0.5 text-xs"
      title={factor.explanation}
    >
      <term.icon aria-hidden className="size-3.5 text-muted-foreground" />
      {term.label}
      <span className="font-mono text-muted-foreground tabular-nums">{factor.score.toFixed(2)}</span>
    </span>
  )
}

export function StaleBadge() {
  return (
    <span
      className={cn('inline-flex h-5.5 items-center gap-1 rounded-md border px-1.5 text-xs font-medium', toneBadgeClass.warning)}
      title="The evidence changed and this relationship is no longer found. The review decision is kept for the record."
    >
      <History aria-hidden className="size-3.5" /> No longer found
    </span>
  )
}

function EvidenceSide({ side, caseRef }: { side: Correlation['evidenceA']; caseRef: string }) {
  const term = evidenceTypeTerms[side.evidenceType as EvidenceType] ?? evidenceTypeTerms.other
  return (
    <div className="flex min-w-0 items-center gap-2">
      <term.icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
      <EvidenceChip reference={side.reference} caseRef={caseRef} />
      <span className="truncate text-sm text-muted-foreground" title={side.description}>
        {side.description || term.label}
      </span>
    </div>
  )
}

/** "CCTV-001 ⟷ VEH-001": the two evidence items a correlation links. */
export function EvidencePair({ correlation, caseRef }: { correlation: Correlation; caseRef: string }) {
  return (
    <div className="grid min-w-0 gap-1 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-center sm:gap-3">
      <EvidenceSide side={correlation.evidenceA} caseRef={caseRef} />
      <ArrowLeftRight aria-label="related to" className="hidden size-4 text-muted-foreground sm:block" />
      <EvidenceSide side={correlation.evidenceB} caseRef={caseRef} />
    </div>
  )
}

/** One row in a list of correlations. */
export function CorrelationRow({ correlation, caseRef }: { correlation: Correlation; caseRef: string }) {
  return (
    <li className={cn('space-y-2 py-3', correlation.reviewStatus === 'rejected' && 'opacity-60')}>
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to={`/investigations/${caseRef}/correlations/${correlation.reference}`}
          className="font-mono text-sm font-medium text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
        >
          {correlation.reference}
        </Link>
        <LevelBadge level={correlation.level} score={correlation.score} />
        <StatusBadge kind="review" status={correlation.reviewStatus} />
        {correlation.stale && <StaleBadge />}
        <Link
          to={`/investigations/${caseRef}/correlations/${correlation.reference}`}
          className="ml-auto text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Why? →
        </Link>
      </div>
      <EvidencePair correlation={correlation} caseRef={caseRef} />
      <div className="flex flex-wrap gap-1.5">
        {correlation.factors.map((f) => (
          <FactorChip key={f.kind} factor={f} />
        ))}
      </div>
    </li>
  )
}
