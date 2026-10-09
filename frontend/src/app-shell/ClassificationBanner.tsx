import { ShieldAlert } from 'lucide-react'

/**
 * The handling marking every screen carries, as on real case-management systems: who may
 * look at this, and that looking is recorded. Development builds also say the data is made up.
 */
export function ClassificationBanner() {
  return (
    <div
      role="note"
      aria-label="Handling notice"
      data-print="hide"
      className="flex h-6 items-center justify-center gap-1.5 border-b border-warning/30 bg-warning/10 px-3 text-[0.68rem] font-medium tracking-wide text-warning uppercase"
    >
      <ShieldAlert aria-hidden className="size-3" />
      <span>Restricted · authorised investigators only · every action is recorded</span>
      {import.meta.env.DEV && <span className="hidden normal-case sm:inline">· demo data is fictional</span>}
    </div>
  )
}
