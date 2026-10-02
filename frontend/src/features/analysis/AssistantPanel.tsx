import { useEffect, useRef, useState } from 'react'
import { Bot, ChevronRight, CircleStop, LoaderCircle, Search, Send, TriangleAlert, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import type { AssistantEvent, AssistantTurn } from '@/domain/types'
import { AIService } from '@/services/aiService'
import { ApiError } from '@/services/apiClient'
import { AIAssistedLabel, CitationSummary, CitedText } from './components'

type ToolEvent = Extract<AssistantEvent, { type: 'tool_result' }>
type Answer = Extract<AssistantEvent, { type: 'answer' }>

interface Exchange {
  question: string
  steps: ToolEvent[]
  pendingTool: string | null
  status: string
  answer: Answer | null
  error: string | null
  startedAt: number
}

const TOOL_LABELS: Record<string, string> = {
  search_entities: 'Searched entities',
  get_entity: 'Opened entity',
  search_events: 'Searched events',
  get_evidence: 'Read evidence',
  list_correlations: 'Checked correlations',
  find_connection: 'Traced the connection',
  search_documents: 'Searched documents by meaning',
}

/** Wall-clock time, read in event handlers and timers only (never while rendering). */
const timestamp = () => Date.now()

const SUGGESTIONS = [
  'What do we know about the vehicle ZZ99 ZZ 0001?',
  'Who did phone PH001 call that evening?',
  'Which evidence places device D001 near the warehouse?',
  'Summarise the strongest correlations and what supports them.',
]

/** The Investigation Assistant: ask in plain words; it looks things up and cites evidence. */
export function AssistantPanel({ caseRef }: { caseRef: string }) {
  const [question, setQuestion] = useState('')
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [running, setRunning] = useState(false)
  const [now, setNow] = useState(timestamp)
  const abort = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => setNow(timestamp()), 1000)
    return () => clearInterval(timer)
  }, [running])
  useEffect(() => () => abort.current?.abort(), [])

  const update = (change: (current: Exchange) => Exchange) =>
    setExchanges((list) => [...list.slice(0, -1), change(list[list.length - 1])])

  async function ask(text: string) {
    const trimmed = text.trim()
    if (!trimmed || running) return
    // Earlier answered turns give the assistant context for follow-up questions.
    const history: AssistantTurn[] = exchanges
      .filter((e) => e.answer)
      .slice(-3)
      .flatMap((e) => [
        { role: 'user' as const, content: e.question },
        { role: 'assistant' as const, content: e.answer!.text },
      ])
    setExchanges((list) => [
      ...list,
      { question: trimmed, steps: [], pendingTool: null, status: 'Starting…', answer: null, error: null, startedAt: timestamp() },
    ])
    setQuestion('')
    setRunning(true)
    setNow(timestamp())
    abort.current = new AbortController()
    requestAnimationFrame(() => bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }))
    try {
      for await (const event of AIService.ask(caseRef, trimmed, history, abort.current.signal)) {
        if (event.type === 'status') update((e) => ({ ...e, status: event.message }))
        else if (event.type === 'tool_start') update((e) => ({ ...e, pendingTool: event.name, status: `${TOOL_LABELS[event.name] ?? event.name}…` }))
        else if (event.type === 'tool_result') update((e) => ({ ...e, pendingTool: null, steps: [...e.steps, event] }))
        else if (event.type === 'answer') update((e) => ({ ...e, answer: event }))
        else if (event.type === 'error') update((e) => ({ ...e, error: event.message }))
      }
      if (abort.current.signal.aborted) update((e) => (e.answer ? e : { ...e, error: 'Stopped.' }))
    } catch (error) {
      update((e) => ({ ...e, error: error instanceof ApiError ? error.message : 'The assistant could not be reached.' }))
    } finally {
      setRunning(false)
      abort.current = null
    }
  }

  return (
    <div className="space-y-4">
      {exchanges.length === 0 && (
        <Card>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Ask a question in plain words. The assistant looks things up in this investigation with read-only tools, as you, and cites the
              evidence for every statement. It runs on this computer: the first answer can take a few minutes, later ones about a minute.
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <Button key={s} variant="outline" size="sm" className="h-auto py-1.5 text-left whitespace-normal" onClick={() => ask(s)}>
                  {s}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <ol className="space-y-4" aria-live="polite">
        {exchanges.map((exchange, i) => (
          <li key={i} className="space-y-3">
            <div className="flex items-start gap-2">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted"><User aria-hidden className="size-4" /></span>
              <p className="pt-1 text-sm font-medium">{exchange.question}</p>
            </div>
            <Card className="gap-3 py-4">
              <CardContent className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-inferred/15"><Bot aria-hidden className="size-4 text-inferred" /></span>
                  <span className="text-sm font-medium">Investigation Assistant</span>
                  {exchange.answer && <AIAssistedLabel />}
                </div>

                {exchange.steps.length > 0 && (
                  <details className="group rounded-md border bg-muted/30 px-3 py-2 text-xs" open={!exchange.answer}>
                    <summary className="flex cursor-pointer list-none items-center gap-1 font-medium text-muted-foreground">
                      <ChevronRight aria-hidden className="size-3.5 transition-transform group-open:rotate-90" />
                      How I found this: {exchange.steps.length} lookup{exchange.steps.length === 1 ? '' : 's'}
                    </summary>
                    <ol className="mt-2 space-y-1.5">
                      {exchange.steps.map((step, s) => (
                        <li key={s} className="flex gap-2">
                          <Search aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                          <span>
                            <strong>{TOOL_LABELS[step.name] ?? step.name}</strong>{' '}
                            <span className="font-mono text-muted-foreground">{formatArguments(step.arguments)}</span>
                            <span className="block text-muted-foreground">→ {step.summary || 'done'} · {(step.duration_ms / 1000).toFixed(1)} s</span>
                          </span>
                        </li>
                      ))}
                    </ol>
                  </details>
                )}

                {exchange.answer ? (
                  <>
                    <CitedText caseRef={caseRef} text={exchange.answer.text} citations={exchange.answer.citations} />
                    <CitationSummary citations={exchange.answer.citations} />
                    <p className="text-xs text-muted-foreground">
                      {exchange.answer.model} · {exchange.answer.steps} step{exchange.answer.steps === 1 ? '' : 's'} · {Math.round(exchange.answer.duration_ms / 1000)} s.
                      Possible links are not proof; check the cited evidence.
                    </p>
                  </>
                ) : exchange.error ? (
                  <p className="flex items-start gap-2 text-sm text-warning"><TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" /> {exchange.error}</p>
                ) : (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                    <LoaderCircle aria-hidden className="size-4 animate-spin" />
                    {exchange.status} <span className="font-mono tabular-nums">{Math.max(0, Math.round((now - exchange.startedAt) / 1000))} s</span>
                  </p>
                )}
              </CardContent>
            </Card>
          </li>
        ))}
      </ol>
      <div ref={bottom} />

      <form
        className="sticky bottom-0 flex items-end gap-2 rounded-lg border bg-card p-2 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault()
          ask(question)
        }}
      >
        <Textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              ask(question)
            }
          }}
          placeholder="Ask about this investigation…"
          aria-label="Question for the Investigation Assistant"
          maxLength={1000}
          rows={1}
          className="max-h-40 min-h-9 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
        />
        {running ? (
          <Button type="button" variant="outline" onClick={() => abort.current?.abort()}><CircleStop /> Stop</Button>
        ) : (
          <Button type="submit" disabled={!question.trim()}><Send /> Ask</Button>
        )}
      </form>
    </div>
  )
}

function formatArguments(args: Record<string, unknown>): string {
  return Object.entries(args)
    .filter(([, v]) => v !== '' && v != null)
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${String(v)}`)
    .join(' · ')
}
