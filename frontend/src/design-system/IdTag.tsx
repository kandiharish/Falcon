import { cn } from '@/lib/utils'

/** Monospaced identifier chip for evidence, entity, event and case IDs (e.g. CCTV-001). */
export function IdTag({ children, className }: { children: string; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex h-5.5 items-center rounded border bg-muted/60 px-1.5 font-mono text-[0.72rem] font-medium tracking-tight text-foreground',
        className,
      )}
    >
      {children}
    </span>
  )
}
