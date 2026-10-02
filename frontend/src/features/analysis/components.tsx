/**
 * Building blocks for AI-assisted screens. Every AI output is labelled, cites its sources,
 * and flags any source it could not verify (plan §22: "never present AI output as truth").
 */
import { Fragment } from 'react'
import { Link } from 'react-router'
import { Bot, CircleAlert, CircleCheck, Cpu, TriangleAlert } from 'lucide-react'
import type { Citation } from '@/domain/types'
import { useAIStatus } from '@/services/queries'
import { cn } from '@/lib/utils'
import { refLink, splitCitations } from './refs'

export function AIAssistedLabel({ className }: { className?: string }) {
  return (
    <span
      className={cn('inline-flex h-5.5 items-center gap-1 rounded-md border border-inferred/25 bg-inferred/10 px-1.5 text-xs font-medium text-inferred', className)}
      title="Produced with the local AI model. Check it against the cited evidence before relying on it."
    >
      <Bot aria-hidden className="size-3.5" /> AI-assisted · Requires review
    </span>
  )
}

/** "Local AI ready · qwen3:8b", or why it is not. */
export function AIStatusNote() {
  const { data, isPending } = useAIStatus()
  if (isPending) return null
  if (!data) {
    return <StatusLine tone="warn" text="The AI status could not be checked." />
  }
  return data.available ? (
    <StatusLine tone="ok" text={`Local AI ready · ${data.chat_model} · runs on this computer, nothing leaves it`} />
  ) : (
    <StatusLine tone="warn" text={data.message} />
  )
}

function StatusLine({ tone, text }: { tone: 'ok' | 'warn'; text: string }) {
  return (
    <p className={cn('inline-flex items-center gap-1.5 text-xs', tone === 'ok' ? 'text-muted-foreground' : 'text-warning')}>
      {tone === 'ok' ? <Cpu aria-hidden className="size-3.5" /> : <TriangleAlert aria-hidden className="size-3.5" />}
      {text}
    </p>
  )
}

/** A reference chip: links to its page; unverified ones are flagged. */
export function RefChip({ caseRef, reference, verified = true }: { caseRef: string; reference: string; verified?: boolean }) {
  const href = refLink(caseRef, reference)
  const className = cn(
    'inline-flex items-center gap-0.5 rounded border px-1 align-baseline font-mono text-[0.72rem] font-medium whitespace-nowrap',
    verified ? 'bg-muted/60' : 'border-warning/40 bg-warning/10 text-warning',
  )
  const title = verified
    ? 'Returned by FALCON while answering'
    : 'Not returned by any lookup while answering: possibly invented. Check it.'
  const content = (
    <>
      {!verified && <CircleAlert aria-hidden className="size-3" />}
      {reference}
    </>
  )
  return href ? (
    <Link to={href} className={cn(className, 'outline-none hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring')} title={title}>
      {content}
    </Link>
  ) : (
    <span className={className} title={title}>{content}</span>
  )
}

/** Answer text with every [REF] turned into a chip. */
export function CitedText({ caseRef, text, citations }: { caseRef: string; text: string; citations: Citation[] }) {
  const verified = new Map(citations.map((c) => [c.reference, c.verified]))
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {text.split(/\n{2,}/).map((paragraph, p) => (
        <p key={p} className="whitespace-pre-line">
          {splitCitations(paragraph).map((part, i) =>
            'ref' in part ? (
              <RefChip key={i} caseRef={caseRef} reference={part.ref} verified={verified.get(part.ref) ?? false} />
            ) : (
              <Fragment key={i}>{part.text}</Fragment>
            ),
          )}
        </p>
      ))}
    </div>
  )
}

export function CitationSummary({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-warning">
        <TriangleAlert aria-hidden className="size-3.5" /> No evidence was cited. Treat this answer with caution.
      </p>
    )
  }
  const unverified = citations.filter((c) => !c.verified)
  return unverified.length === 0 ? (
    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <CircleCheck aria-hidden className="size-3.5 text-success" /> All {citations.length} cited IDs were returned by FALCON lookups.
    </p>
  ) : (
    <p className="flex items-center gap-1.5 text-xs text-warning">
      <CircleAlert aria-hidden className="size-3.5" />
      {unverified.map((c) => c.reference).join(', ')} {unverified.length === 1 ? 'was' : 'were'} not returned by any lookup. Check before relying on {unverified.length === 1 ? 'it' : 'them'}.
    </p>
  )
}
