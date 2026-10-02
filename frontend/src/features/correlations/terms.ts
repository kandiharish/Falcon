/** Words, tones and icons for correlation strength and factors. */
import { Clock, Fingerprint, MapPin, type LucideIcon } from 'lucide-react'
import type { CorrelationLevel, FactorKind } from '@/domain/types'
import type { Tone } from '@/design-system/tones'

export const levelTerms: Record<CorrelationLevel, { label: string; tone: Tone; bars: number }> = {
  high: { label: 'High', tone: 'success', bars: 3 },
  medium: { label: 'Medium', tone: 'warning', bars: 2 },
  low: { label: 'Low', tone: 'neutral', bars: 1 },
}

export const factorTerms: Record<FactorKind, { label: string; icon: LucideIcon; question: string }> = {
  entity: { label: 'Shared entity', icon: Fingerprint, question: 'Do both contain the same phone, vehicle, device or person?' },
  time: { label: 'Close in time', icon: Clock, question: 'Did their events happen within 30 minutes of each other?' },
  location: { label: 'Close in place', icon: MapPin, question: 'Did their events happen within 500 m of each other?' },
}
