import { Check, ChevronsUpDown, FolderSearch } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { useInvestigationContext } from '@/app/investigation-context'
import { can } from '@/services/authService'
import { useCurrentUser, useInvestigations } from '@/services/queries'
import { StatusBadge } from '@/design-system/badges'

/** "Current Investigation" selector in the top bar (plan §7). */
export function InvestigationSwitcher() {
  const { data: user } = useCurrentUser()
  const allowed = can(user, 'investigation:read')
  const { data: page, isPending } = useInvestigations({ limit: 50 }, allowed)
  const investigations = page?.items
  const { currentInvestigationId, setCurrentInvestigation } = useInvestigationContext()
  const current = investigations?.find((i) => i.reference === currentInvestigationId)

  if (!allowed) return null
  if (isPending) return <Skeleton className="h-8 w-56" />

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="max-w-72 justify-between gap-2 font-normal">
          <FolderSearch className="text-muted-foreground" />
          <span className="font-mono text-xs">{current?.reference ?? 'Select investigation'}</span>
          <span className="hidden truncate text-muted-foreground xl:inline">{current?.title}</span>
          <ChevronsUpDown className="text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-96">
        <DropdownMenuLabel>Switch investigation</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {investigations?.map((investigation) => (
          <DropdownMenuItem
            key={investigation.reference}
            onSelect={() => setCurrentInvestigation(investigation.reference)}
            className="items-start gap-2 py-2"
          >
            <Check
              className={
                investigation.reference === currentInvestigationId ? 'mt-0.5 opacity-100' : 'mt-0.5 opacity-0'
              }
            />
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs">{investigation.reference}</span>
                <StatusBadge kind="investigation" status={investigation.status} />
              </div>
              <p className="truncate text-sm">{investigation.title}</p>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
