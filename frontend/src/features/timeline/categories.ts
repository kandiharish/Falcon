import type { EventType, InvestigationEvent } from '@/domain/types'

/**
 * Event categories give the timeline and map a small, readable colour set.
 * Colour is never the only signal: lanes, icons and labels say the same thing (plan §36).
 */
export type Category = 'communication' | 'movement' | 'detection' | 'financial' | 'record' | 'other'

export const CATEGORY_OF: Record<EventType, Category> = {
  call_made: 'communication',
  message_sent: 'communication',
  communication: 'communication',
  location_recorded: 'movement',
  person_entered_location: 'movement',
  vehicle_detected: 'detection',
  person_detected: 'detection',
  device_detected: 'detection',
  transaction_completed: 'financial',
  photo_taken: 'record',
  video_recorded: 'record',
  document_created: 'record',
  digital_artifact_created: 'record',
  other: 'other',
}

export const CATEGORY_STYLE: Record<Category, { label: string; color: string }> = {
  communication: { label: 'Communication', color: 'var(--chart-1)' },
  movement: { label: 'Movement / location', color: 'var(--chart-2)' },
  detection: { label: 'Detection', color: 'var(--chart-4)' },
  financial: { label: 'Financial', color: 'var(--chart-3)' },
  record: { label: 'Photo / video / document', color: 'var(--chart-5)' },
  other: { label: 'Other', color: 'var(--muted-foreground)' },
}

export const categoryColor = (event: InvestigationEvent) => CATEGORY_STYLE[CATEGORY_OF[event.eventType]].color
