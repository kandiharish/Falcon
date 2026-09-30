/** Semantic colour "tones". Components pick a tone; the tokens in index.css decide the colour. */
export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'signal' | 'inferred'

export const toneBadgeClass: Record<Tone, string> = {
  neutral: 'border-border bg-muted text-muted-foreground',
  info: 'border-info/25 bg-info/10 text-info',
  success: 'border-success/25 bg-success/10 text-success',
  warning: 'border-warning/30 bg-warning/12 text-warning',
  danger: 'border-destructive/25 bg-destructive/10 text-destructive',
  signal: 'border-signal/30 bg-signal/10 text-signal',
  inferred: 'border-inferred/25 bg-inferred/10 text-inferred',
}

export const toneTextClass: Record<Tone, string> = {
  neutral: 'text-muted-foreground',
  info: 'text-info',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-destructive',
  signal: 'text-signal',
  inferred: 'text-inferred',
}

export const toneFillClass: Record<Tone, string> = {
  neutral: 'bg-muted-foreground',
  info: 'bg-info',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-destructive',
  signal: 'bg-signal',
  inferred: 'bg-inferred',
}
