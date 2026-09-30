/** FALCON logo mark: a stylised falcon wing over a connected node. */
export function FalconMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} role="img" aria-label="FALCON">
      <rect width="32" height="32" rx="7" className="fill-sidebar-accent" />
      <path d="M6 21 16 8l10 13-10-4z" className="fill-sidebar-primary" />
      <circle cx="16" cy="23" r="2" className="fill-sidebar-accent-foreground" />
    </svg>
  )
}
