import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { FolderSearch, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import { Kbd, KbdGroup } from '@/components/ui/kbd'
import { visibleNavigation } from '@/app/navigation'
import { useInvestigationContext } from '@/app/investigation-context'
import { can } from '@/services/authService'
import { useCurrentUser, useInvestigations } from '@/services/queries'

/**
 * Global search (plan §28), opened with Ctrl+K / ⌘K.
 * Phase 2: jump to modules and investigations. Phase 11: full-text search across evidence.
 */
export function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { data: user } = useCurrentUser()
  const canSeeInvestigations = can(user, 'investigation:read')
  const { data: page } = useInvestigations({ limit: 50 }, canSeeInvestigations)
  const investigations = page?.items
  const setCurrentInvestigation = useInvestigationContext((s) => s.setCurrentInvestigation)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen((value) => !value)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const go = (path: string) => {
    setOpen(false)
    navigate(path)
  }

  return (
    <>
      <Button
        variant="outline"
        onClick={() => setOpen(true)}
        aria-label="Search"
        className="size-8 p-0 font-normal text-muted-foreground sm:h-8 sm:w-full sm:max-w-sm sm:justify-start sm:gap-2 sm:px-2.5"
      >
        <Search />
        <span className="hidden flex-1 text-left sm:inline">Search FALCON…</span>
        <KbdGroup className="hidden sm:inline-flex">
          <Kbd>Ctrl</Kbd>
          <Kbd>K</Kbd>
        </KbdGroup>
      </Button>

      <CommandDialog open={open} onOpenChange={setOpen} title="Global search"
        description="Jump to an investigation or a FALCON module."
      >
        {/* cmdk items must live inside <Command>; the dialog is only the frame */}
        <Command>
          <CommandInput placeholder="Type a module name or case ID…" />
          <CommandList>
            <CommandEmpty>
              No matches. Full search across evidence, entities and events arrives in Phase 11.
            </CommandEmpty>
            {canSeeInvestigations && (
              <>
                <CommandGroup heading="Investigations">
                  {investigations?.map((investigation) => (
                    <CommandItem
                      key={investigation.reference}
                      value={`${investigation.reference} ${investigation.title}`}
                      onSelect={() => {
                        setCurrentInvestigation(investigation.reference)
                        go(`/investigations/${investigation.reference}`)
                      }}
                    >
                      <FolderSearch />
                      <span className="font-mono text-xs">{investigation.reference}</span>
                      <span className="truncate">{investigation.title}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
                <CommandSeparator />
              </>
            )}
            {visibleNavigation(user?.permissions ?? []).map((group) => (
              <CommandGroup key={group.label} heading={group.label}>
                {group.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <CommandItem key={item.id} value={item.label} onSelect={() => go(item.path)}>
                      <Icon />
                      {item.label}
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  )
}
