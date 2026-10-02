import { useState } from 'react'
import { ArrowRight, Info, LoaderCircle, Search, SearchX } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import type { AISearchDto } from '@/api/types'
import { ApiError } from '@/services/apiClient'
import { useAISearch } from '@/services/queries'
import { toEvent } from '@/services/extractionService'
import { StatusBadge } from '@/design-system/badges'
import { ConfidenceIndicator } from '@/design-system/ConfidenceIndicator'
import { EmptyState } from '@/design-system/states'
import type { EntityType, ReviewStatus } from '@/domain/types'
import { EntityChip, EventRow, EvidenceChip } from '@/features/extraction/components'
import { useCaseAccess } from '@/features/extraction/useCaseAccess'
import { relationshipTerms } from '@/features/graph/terms'
import { AIAssistedLabel } from './components'

const EXAMPLES = [
  'Show events between 8 PM and 10 PM',
  'Show all communications involving PH001',
  'Which evidence is connected to vehicle V001?',
  'Find relationships between PH004 and V001',
  'Anything about someone forcing a door',
]

/** Natural-language search (plan §23): the question becomes filters; the filters find records. */
export function SearchPanel({ caseRef }: { caseRef: string }) {
  const [question, setQuestion] = useState('')
  const search = useAISearch(caseRef)
  const run = (text: string) => {
    const trimmed = text.trim()
    if (trimmed.length < 2) return
    setQuestion(trimmed)
    search.mutate(trimmed)
  }

  return (
    <div className="space-y-4">
      <form className="flex gap-2" role="search" onSubmit={(e) => { e.preventDefault(); run(question) }}>
        <div className="relative flex-1">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} className="pl-8"
            placeholder="e.g. Show all communications involving PH001" aria-label="Search this investigation in plain words" />
        </div>
        <Button type="submit" disabled={search.isPending || question.trim().length < 2}>
          {search.isPending ? <LoaderCircle className="animate-spin" /> : <Search />} Search
        </Button>
      </form>
      <div className="flex flex-wrap gap-1.5">
        {EXAMPLES.map((example) => (
          <Button key={example} size="xs" variant="outline" onClick={() => run(example)} disabled={search.isPending}>{example}</Button>
        ))}
      </div>

      {search.isPending && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <LoaderCircle aria-hidden className="size-4 animate-spin" /> Reading the question with the local AI… (the first search can take a minute)
        </p>
      )}
      {search.isError && (
        <p className="text-sm text-destructive">{search.error instanceof ApiError ? search.error.message : 'The search failed.'}</p>
      )}
      {search.data && !search.isPending && <Results caseRef={caseRef} result={search.data} />}
    </div>
  )
}

function Results({ caseRef, result }: { caseRef: string; result: AISearchDto }) {
  const { canReview } = useCaseAccess(caseRef)
  const plan = result.plan
  const count = result.events.length + result.evidence.length + result.entities.length + result.path.length + result.passages.length
  const nodeOf = new Map(result.path_nodes.map((n) => [n.id, n]))
  return (
    <div className="space-y-4">
      <Card className="gap-2 py-4">
        <CardContent className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">How FALCON read your question</span>
            {result.interpreted_by === 'rules' ? (
              <span className="text-xs text-muted-foreground">(simple rules: the local AI is not running)</span>
            ) : (
              <AIAssistedLabel />
            )}
          </div>
          <p className="text-sm font-medium">{result.summary}</p>
          <div className="flex flex-wrap gap-1.5 text-xs">
            <PlanChip label="Looking for" value={plan.intent} />
            {[...(plan.entity_refs ?? []), ...(plan.evidence_refs ?? [])].map((r) => <PlanChip key={r} label="ID" value={r} />)}
            {(plan.event_types ?? []).map((t) => <PlanChip key={t} label="Event" value={t.replace(/_/g, ' ')} />)}
            {(plan.evidence_types ?? []).map((t) => <PlanChip key={t} label="Evidence" value={t.replace(/_/g, ' ')} />)}
            {(plan.time_from || plan.time_to) && <PlanChip label="Time of day" value={`${plan.time_from ?? '00:00'}–${plan.time_to ?? '23:59'}`} />}
            {(plan.date_from || plan.date_to) && <PlanChip label="Dates" value={`${plan.date_from ?? '…'} → ${plan.date_to ?? '…'}`} />}
          </div>
          {result.notes.map((note) => (
            <p key={note} className="flex items-start gap-1.5 text-xs text-warning"><Info aria-hidden className="mt-0.5 size-3.5 shrink-0" /> {note}</p>
          ))}
          <p className="text-xs text-muted-foreground">
            Only the reading of the question is AI-assisted. The results below are records from the evidence database. {count} found in {(result.duration_ms / 1000).toFixed(1)} s.
          </p>
        </CardContent>
      </Card>

      {count === 0 && <EmptyState icon={SearchX} title="Nothing found" description="No records match how the question was read. Try naming an ID (like PH001) or a time." />}

      {result.events.length > 0 && (
        <Section title={`Events (${result.events.length})`}>
          <ol className="divide-y">
            {result.events.map((e) => <EventRow key={e.reference} event={toEvent(e)} caseRef={caseRef} canReview={canReview} />)}
          </ol>
        </Section>
      )}

      {result.evidence.length > 0 && (
        <Section title={`Evidence (${result.evidence.length})`}>
          <ul className="divide-y">
            {result.evidence.map((e) => (
              <li key={e.reference} className="flex items-center gap-2 py-2 text-sm">
                <EvidenceChip reference={e.reference} caseRef={caseRef} />
                <span className="truncate">{e.description}</span>
                <span className="ml-auto text-xs text-muted-foreground">{e.evidence_type.replace(/_/g, ' ')}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {result.entities.length > 0 && (
        <Section title={`Entities (${result.entities.length})`}>
          <div className="flex flex-wrap gap-1.5">
            {result.entities.map((e) => (
              <EntityChip key={e.reference} caseRef={caseRef} entity={{ reference: e.reference, entityType: e.entity_type as EntityType, label: e.label }} />
            ))}
          </div>
        </Section>
      )}

      {result.path.length > 0 && (
        <Section title={`Chain of links (${result.path.length} step${result.path.length === 1 ? '' : 's'})`}>
          <ol className="space-y-3">
            {result.path.map((edge, i) => {
              const from = nodeOf.get(edge.source)
              const to = nodeOf.get(edge.target)
              return (
                <li key={edge.id} className="space-y-1 rounded-md border p-3 text-sm">
                  <p className="flex flex-wrap items-center gap-1.5 font-medium">
                    <span className="text-xs text-muted-foreground">{i + 1}.</span>
                    <span className="font-mono text-xs">{from?.reference}</span> {from?.label}
                    <ArrowRight aria-hidden className="size-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">{relationshipTerms[edge.type].label}</span>
                    <ArrowRight aria-hidden className="size-3.5 text-muted-foreground" />
                    <span className="font-mono text-xs">{to?.reference}</span> {to?.label}
                  </p>
                  <p className="text-muted-foreground">{edge.why}</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <ConfidenceIndicator score={edge.confidence} />
                    <StatusBadge kind="review" status={edge.review_status as ReviewStatus} />
                    {edge.supporting_evidence.map((r) => <EvidenceChip key={r} reference={r} caseRef={caseRef} />)}
                  </div>
                </li>
              )
            })}
          </ol>
        </Section>
      )}

      {result.passages.length > 0 && (
        <Section title={`Passages with a similar meaning (${result.passages.length})`} label>
          <ul className="space-y-3">
            {result.passages.map((p) => (
              <li key={p.evidence.reference} className="space-y-1 text-sm">
                <p className="flex items-center gap-2">
                  <EvidenceChip reference={p.evidence.reference} caseRef={caseRef} />
                  <span className="truncate text-muted-foreground">{p.evidence.description}</span>
                  <span className="ml-auto font-mono text-xs text-muted-foreground" title="Similarity of meaning, 0–1">similarity {p.score.toFixed(2)}</span>
                </p>
                <blockquote className="border-l-2 pl-3 text-muted-foreground">{p.passage}</blockquote>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}

function PlanChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border bg-muted/50 px-1.5 py-0.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </span>
  )
}

function Section({ title, label, children }: { title: string; label?: boolean; children: React.ReactNode }) {
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="flex flex-row items-center gap-2">
        <CardTitle className="text-base">{title}</CardTitle>
        {label && <AIAssistedLabel />}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
