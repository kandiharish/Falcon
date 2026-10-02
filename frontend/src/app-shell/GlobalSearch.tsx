import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import {
  Activity,
  FileStack,
  FileText,
  FolderSearch,
  ListChecks,
  Search,
  UserRoundSearch,
  Waypoints,
  type LucideIcon,
} from 'lucide-react'
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
import { useCurrentUser, useGlobalSearch, useInvestigations } from '@/services/queries'

const HIT_KINDS: Record<string, { label: string; icon: LucideIcon }> = {
  investigation: { label: 'Investigations', icon: FolderSearch },
  evidence: { label: 'Evidence', icon: FileStack },
  entity: { label: 'Entities', icon: UserRoundSearch },
  event: { label: 'Events', icon: Activity },
  correlation: { label: 'Correlations', icon: Waypoints },
  task: { label: 'Tasks', icon: ListChecks },
  report: { label: 'Reports', icon: FileText },
}
const HIT_ORDER = Object.keys(HIT_KINDS)

/** The value, but only after it has stopped changing for `delay` ms (no request per keystroke). */
function useDebounced<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return settled
}

/**
 * Global search (plan §28), opened with Ctrl+K / ⌘K: every investigation record you may see,
 * plus investigations and FALCON modules to jump to.
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

  const [text, setText] = useState('')
  const query = useDebounced(text.trim(), 250)
  const { data: found, isFetching: searching } = useGlobalSearch(canSeeInvestigations ? query : '')
  const hits = query.length >= 2 ? (found ?? []) : []
  const needle = text.trim().toLowerCase()
  const matches = (value: string) => !needle || value.toLowerCase().includes(needle)
  const matchingCases = (investigations ?? []).filter((i) => matches(`${i.reference} ${i.title}`)).slice(0, needle ? 5 : 8)
  const modules = visibleNavigation(user?.permissions ?? [])
    .map((group) => ({ ...group, items: group.items.filter((item) => matches(item.label)) }))
    .filter((group) => group.items.length > 0)

  const go = (path: string) => {
    setOpen(false)
    setText('')
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
        description="Search investigations, evidence, entities, events, tasks and reports."
      >
        {/* We filter ourselves (shouldFilter=false): server results are already matches. */}
        <Command shouldFilter={false}>
          <CommandInput value={text} onValueChange={setText} placeholder="Search IDs, names, numbers, places… (2+ characters)" />
          <CommandList>
            <CommandEmpty>
              {query.length >= 2 ? (searching ? 'Searching…' : `Nothing found for “${query}”.`) : 'Type at least 2 characters.'}
            </CommandEmpty>
            {query.length >= 2 &&
              HIT_ORDER.filter((kind) => hits.some((h) => h.kind === kind)).map((kind) => (
                <CommandGroup key={kind} heading={HIT_KINDS[kind].label}>
                  {hits.filter((h) => h.kind === kind).map((hit) => {
                    const Icon = HIT_KINDS[kind].icon
                    return (
                      <CommandItem
                        key={`${hit.kind}-${hit.investigation_reference}-${hit.reference}`}
                        value={`${hit.kind}-${hit.investigation_reference}-${hit.reference}`}
                        onSelect={() => {
                          setCurrentInvestigation(hit.investigation_reference)
                          go(hit.link)
                        }}
                      >
                        <Icon />
                        <span className="min-w-0 flex-1">
                          <span className="flex gap-2">
                            <span className="shrink-0 font-mono text-xs leading-5">{hit.reference}</span>
                            <span className="truncate">{hit.title}</span>
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">{hit.subtitle}</span>
                        </span>
                      </CommandItem>
                    )
                  })}
                </CommandGroup>
              ))}
            {canSeeInvestigations && matchingCases.length > 0 && (
              <>
                <CommandGroup heading="Switch investigation">
                  {matchingCases.map((investigation) => (
                    <CommandItem
                      key={investigation.reference}
                      value={`case-${investigation.reference}`}
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
            {modules.map((group) => (
              <CommandGroup key={group.label} heading={group.label}>
                {group.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <CommandItem key={item.id} value={`module-${item.id}`} onSelect={() => go(item.path)}>
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
