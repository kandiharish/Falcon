import { useState } from 'react'
import { Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { EventType } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useAddAnnotation, useEntities } from '@/services/queries'
import { annotationEventTypes, eventTypeTerms } from '@/design-system/vocabulary'
import { localInputToUtc } from '@/lib/time'
import { useCaseTimeZone } from './useCaseAccess'

interface Props {
  caseRef: string
  evidenceRef: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * An analyst records what they observe in a piece of evidence ("person at the rear door at
 * 20:30:02"). Saved as USER ENTERED, always linked to this evidence, never touched by
 * automatic re-processing.
 */
export function AnnotationDialog({ caseRef, evidenceRef, open, onOpenChange }: Props) {
  const add = useAddAnnotation(caseRef)
  const timeZone = useCaseTimeZone(caseRef)
  const { data: entities } = useEntities(open ? caseRef : null)
  const [eventType, setEventType] = useState<EventType>('person_detected')
  const [occurredAt, setOccurredAt] = useState('')
  const [description, setDescription] = useState('')
  const [locationText, setLocationText] = useState('')
  const [participants, setParticipants] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setEventType('person_detected')
    setOccurredAt('')
    setDescription('')
    setLocationText('')
    setParticipants([])
    setError(null)
    add.reset()
  }

  const submit = () => {
    if (description.trim().length < 3) return setError('Describe what you observed.')
    setError(null)
    add.mutate(
      {
        evidenceReference: evidenceRef,
        eventType,
        occurredAt: occurredAt ? localInputToUtc(occurredAt, timeZone) : null,
        description,
        locationText,
        participants: participants.map((reference) => ({ entityReference: reference, role: 'involved' })),
      },
      {
        onSuccess: (event) => {
          toast.success(`${event.reference} recorded`, { description: 'Saved as user-entered, linked to ' + evidenceRef })
          reset()
          onOpenChange(false)
        },
      },
    )
  }

  const message = error ?? (add.error instanceof ApiError ? add.error.message : add.error ? 'The event could not be saved.' : null)

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) reset(); onOpenChange(next) }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Record an observation from {evidenceRef}</DialogTitle>
          <DialogDescription>
            Describe only what the evidence shows. It is saved as “user entered” with your name, and stays
            linked to {evidenceRef} as its supporting evidence.
          </DialogDescription>
        </DialogHeader>
        {message && <p role="alert" className="rounded-md border border-destructive/25 bg-destructive/5 px-3 py-2 text-sm">{message}</p>}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="an-type">What happened</Label>
            <Select value={eventType} onValueChange={(v) => setEventType(v as EventType)}>
              <SelectTrigger id="an-type" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {annotationEventTypes.map((type) => (
                  <SelectItem key={type} value={type}>{eventTypeTerms[type].label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="an-time">When, in {timeZone === 'UTC' ? 'UTC' : timeZone}</Label>
            <Input id="an-time" type="datetime-local" step={1} value={occurredAt} onChange={(e) => setOccurredAt(e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="an-desc">Observation</Label>
            <Textarea id="an-desc" rows={3} placeholder="e.g. Person in a dark jacket opens the rear door; face not visible" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="an-loc">Location <span className="font-normal text-muted-foreground">(optional)</span></Label>
            <Input id="an-loc" value={locationText} onChange={(e) => setLocationText(e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="an-entity">Who or what is involved <span className="font-normal text-muted-foreground">(optional)</span></Label>
            <Select value="" onValueChange={(ref) => setParticipants((p) => (p.includes(ref) ? p : [...p, ref]))}>
              <SelectTrigger id="an-entity" className="w-full"><SelectValue placeholder="Add a known entity…" /></SelectTrigger>
              <SelectContent>
                {entities?.items.map((e) => (
                  <SelectItem key={e.reference} value={e.reference}>{e.reference} · {e.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {participants.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {participants.map((ref) => (
                  <span key={ref} className="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-xs">
                    {ref}
                    <button type="button" aria-label={`Remove ${ref}`} onClick={() => setParticipants((p) => p.filter((r) => r !== ref))}>
                      <X className="size-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={submit} disabled={add.isPending}><Plus /> {add.isPending ? 'Saving…' : 'Record observation'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
