import { CalendarClock, Check } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import type { NavItem } from '@/app/navigation'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState } from '@/design-system/states'

/**
 * A module that is on the roadmap but not built yet.
 * Clearly marked as future functionality (plan §59) — never a silent blank page.
 */
export function UpcomingModulePage({ item }: { item: NavItem }) {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title={item.label} description={item.summary} eyebrow={`Arrives in Phase ${item.phase}`} />
      <EmptyState
        icon={CalendarClock}
        title={`${item.label} is planned for Phase ${item.phase}`}
        description={
          <div className="space-y-3">
            <p>This module is part of the FALCON roadmap. When it is built, it will provide:</p>
            <ul className="mx-auto w-fit space-y-1 text-left">
              {item.capabilities.map((capability) => (
                <li key={capability} className="flex items-start gap-2">
                  <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-primary" />
                  <span>{capability}</span>
                </li>
              ))}
            </ul>
          </div>
        }
        action={
          <Button asChild variant="outline">
            <Link to="/">Back to overview</Link>
          </Button>
        }
      />
    </div>
  )
}
