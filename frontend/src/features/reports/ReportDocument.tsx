/**
 * The report as a document: readable on screen, clean on paper.
 *
 *   PART A  OBSERVED EVIDENCE           what was found and where it came from
 *   PART B  ANALYTICAL INTERPRETATION   what analysts and rules suggest it means
 *   PART C  RECORD                      limitations, audit information, fingerprint
 */
import type { ReactNode } from 'react'
import { entityTypeTerms, evidenceTypeTerms, eventTypeTerms } from '@/design-system/vocabulary'
import type { EntityType, EventType, EvidenceType } from '@/domain/types'
import { formatInZone } from '@/lib/time'
import { cn } from '@/lib/utils'
import type { ReportContent } from './content'

const label = (value: string) => value.replace(/_/g, ' ')

export function ReportDocument({ content, sha256, intact }: { content: ReportContent; sha256: string | null; intact: boolean }) {
  const zone = content.summary.time_zone || 'UTC'
  const at = (iso: string | null, style: 'date' | 'datetime' = 'datetime') =>
    iso
      ? formatInZone(iso, zone, style === 'date' ? { dateStyle: 'medium' } : { dateStyle: 'medium', timeStyle: 'short' })
      : 'not known'
  const { summary, scope } = content
  let section = 0
  const n = () => ++section

  return (
    <article className="mx-auto max-w-4xl space-y-8 rounded-lg border bg-card p-6 text-sm leading-relaxed shadow-sm sm:p-10 print:border-0 print:p-0 print:shadow-none">
      <header className="space-y-2 border-b pb-6">
        <p className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">FALCON investigation report · {content.report.reference}</p>
        <h1 className="text-2xl font-semibold tracking-tight">{content.report.title}</h1>
        <p className="text-muted-foreground">
          {summary.reference} · {summary.title} · generated {at(content.report.generated_at)} by {content.report.generated_by} · times in {zone}
        </p>
        <p className="text-xs text-muted-foreground">
          Confidential. Contains a frozen snapshot of the investigation. {content.report.include_pending ? 'Items awaiting analyst review are included and marked.' : 'Only analyst-confirmed items are included.'}
        </p>
      </header>

      <Section n={n()} title="Investigation summary">
        <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[10rem_1fr]">
          <Row k="Case">{summary.reference} · {summary.title}</Row>
          <Row k="Type">{summary.case_type}</Row>
          <Row k="Status / stage">{label(summary.status)} · {label(summary.stage)} · priority {summary.priority}</Row>
          <Row k="Location">{summary.location || 'not recorded'}</Row>
          <Row k="Lead investigator">{summary.lead}</Row>
          <Row k="Team">{summary.team.join(', ') || 'none'}</Row>
          <Row k="Opened">{at(summary.opened_at, 'date')}</Row>
        </dl>
        {summary.description && <p className="mt-3">{summary.description}</p>}
      </Section>

      <Section n={n()} title="Scope">
        <p>
          Events from <strong>{at(scope.period_from)}</strong> to <strong>{at(scope.period_to)}</strong>: {scope.counts.evidence} evidence items,{' '}
          {scope.counts.entities} entities, {scope.counts.events} events and {scope.counts.correlations} potential relationships.
        </p>
        <p className="mt-1 text-muted-foreground">Included: {scope.included} Excluded: {scope.excluded}</p>
      </Section>

      <Part letter="A" title="Observed evidence" note="What was collected and extracted, with its source. No interpretation." />

      <Section n={n()} title="Evidence overview">
        <Table head={['ID', 'Type', 'Description', 'Collected', 'Status']}>
          {content.evidence.map((e) => (
            <tr key={e.reference}>
              <Td mono>{e.reference}</Td>
              <Td>{evidenceTypeTerms[e.type as EvidenceType]?.label ?? label(e.type)}</Td>
              <Td>{e.description}{e.location ? ` · ${e.location}` : ''}</Td>
              <Td>{at(e.collected_at)}</Td>
              <Td>{label(e.status)}</Td>
            </tr>
          ))}
        </Table>
      </Section>

      <Section n={n()} title="Evidence sources">
        <ul className="flex flex-wrap gap-x-6 gap-y-1">
          {Object.entries(content.sources).map(([type, count]) => (
            <li key={type}>{evidenceTypeTerms[type as EvidenceType]?.label ?? label(type)}: <strong>{count}</strong></li>
          ))}
        </ul>
      </Section>

      <Section n={n()} title="Important entities">
        <Table head={['ID', 'Type', 'Name / value', 'Evidence', 'Events', 'Review']}>
          {content.entities.map((e) => (
            <tr key={e.reference}>
              <Td mono>{e.reference}</Td>
              <Td>{entityTypeTerms[e.type as EntityType]?.label ?? label(e.type)}</Td>
              <Td>{e.label}</Td>
              <Td>{e.evidence_count}</Td>
              <Td>{e.event_count}</Td>
              <Td><Review status={e.review_status} /></Td>
            </tr>
          ))}
        </Table>
      </Section>

      <Section n={n()} title="Event timeline">
        <Table head={['Time', 'ID', 'Event', 'Source', 'How known', 'Review']}>
          {content.timeline.map((e) => (
            <tr key={e.reference}>
              <Td>{at(e.occurred_at)}</Td>
              <Td mono>{e.reference}</Td>
              <Td>
                <strong>{eventTypeTerms[e.type as EventType]?.label ?? label(e.type)}</strong>: {e.description}
                {e.participants.length > 0 && <span className="text-muted-foreground"> · {e.participants.join(', ')}</span>}
              </Td>
              <Td mono>{e.evidence}</Td>
              <Td>{label(e.assertion)} · {e.confidence.toFixed(2)}</Td>
              <Td><Review status={e.review_status} /></Td>
            </tr>
          ))}
        </Table>
      </Section>

      <Section n={n()} title="Supporting evidence and integrity">
        <p className="mb-2 text-muted-foreground">Each original file is identified by its SHA-256 fingerprint, taken on upload. Originals are never modified.</p>
        <Table head={['ID', 'SHA-256', 'Integrity', 'Uploaded']}>
          {content.evidence.map((e) => (
            <tr key={e.reference}>
              <Td mono>{e.reference}</Td>
              <Td mono className="text-[0.7rem] break-all">{e.sha256}</Td>
              <Td>{e.integrity_ok === true ? `verified ${at(e.integrity_checked_at)}` : e.integrity_ok === false ? 'MISMATCH' : 'not checked'}</Td>
              <Td>{e.uploaded_by}, {at(e.uploaded_at)}</Td>
            </tr>
          ))}
        </Table>
      </Section>

      <Part letter="B" title="Analytical interpretation" note="Potential relationships and analyst conclusions. Association is not proof; each item shows its basis and review status." />

      <Section n={n()} title="Correlations">
        {content.correlations.length === 0 ? <p className="text-muted-foreground">None.</p> : (
          <ol className="space-y-3">
            {content.correlations.map((c) => (
              <li key={c.reference} className="print-avoid-break">
                <p><strong className="font-mono">{c.reference}</strong> · {c.evidence_a} ⟷ {c.evidence_b} · {c.level} ({c.score.toFixed(2)}) · <Review status={c.review_status} />
                  {c.reviewed_by && <span className="text-muted-foreground"> by {c.reviewed_by}{c.review_note ? `: “${c.review_note}”` : ''}</span>}
                </p>
                <ul className="ml-5 list-disc text-muted-foreground">
                  {c.reasons.map((r) => <li key={r}>{r}</li>)}
                </ul>
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section n={n()} title="Relationship analysis">
        {content.relationships.length === 0 ? <p className="text-muted-foreground">No links between entities through shared events.</p> : (
          <ul className="ml-5 list-disc space-y-1">
            {content.relationships.map((r) => <li key={`${r.from}-${r.to}-${r.type}`}>{r.why} <Review status={r.review_status} /></li>)}
          </ul>
        )}
      </Section>

      <Section n={n()} title="Analyst notes">
        {content.analyst_notes.written ? <p className="whitespace-pre-line">{content.analyst_notes.written}</p> : <p className="text-muted-foreground">No written notes.</p>}
        {content.analyst_notes.observations.length > 0 && (
          <>
            <p className="mt-3 font-medium">Observations recorded by analysts</p>
            <ul className="ml-5 list-disc">
              {content.analyst_notes.observations.map((o) => (
                <li key={o.reference}><span className="font-mono">{o.reference}</span> ({o.evidence}, {at(o.occurred_at)}): {o.description}</li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <Part letter="C" title="Record" />

      <Section n={n()} title="Limitations">
        <ul className="ml-5 list-disc space-y-1">
          {content.limitations.written && <li className="whitespace-pre-line">{content.limitations.written}</li>}
          {content.limitations.automatic.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </Section>

      <Section n={n()} title="Audit information">
        <p>{content.audit.entries} audit entries for this investigation; last activity {at(content.audit.last_activity)}. {content.audit.note}</p>
        <p className="mt-2 text-muted-foreground">
          {Object.entries(content.audit.by_action).map(([action, count]) => `${action} ×${count}`).join(' · ')}
        </p>
        <div className="mt-4 rounded-md border p-3 print-avoid-break">
          <p className="font-medium">Report fingerprint (SHA-256)</p>
          <p className="font-mono text-xs break-all">{sha256 ?? 'not available'}</p>
          <p className={cn('mt-1 text-xs', intact ? 'text-muted-foreground' : 'font-semibold text-destructive')}>
            {intact
              ? 'Checked when this page was opened: the stored report matches its fingerprint.'
              : 'WARNING: the stored report no longer matches its fingerprint. It may have been altered.'}
          </p>
        </div>
      </Section>
    </article>
  )
}

function Part({ letter, title, note }: { letter: string; title: string; note?: string }) {
  return (
    <div className="border-y-2 border-foreground/80 py-2 print-avoid-break">
      <p className="text-xs font-bold tracking-widest uppercase">Part {letter} · {title}</p>
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
    </div>
  )
}

function Section({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-base font-semibold"><span className="text-muted-foreground">{n}.</span> {title}</h2>
      {children}
    </section>
  )
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{k}</dt>
      <dd>{children}</dd>
    </>
  )
}

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto print:overflow-visible">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b">{head.map((h) => <th key={h} className="py-1.5 pr-3 font-semibold">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y">{children}</tbody>
      </table>
    </div>
  )
}

function Td({ children, mono, className }: { children: ReactNode; mono?: boolean; className?: string }) {
  return <td className={cn('py-1.5 pr-3 align-top', mono && 'font-mono whitespace-nowrap', className)}>{children}</td>
}

function Review({ status }: { status: string }) {
  return status === 'confirmed' ? (
    <span className="text-success">confirmed</span>
  ) : status === 'pending' ? (
    <span className="text-warning">requires review</span>
  ) : (
    <span>{label(status)}</span>
  )
}
