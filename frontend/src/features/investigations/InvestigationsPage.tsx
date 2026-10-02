import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { ChevronLeft, ChevronRight, FolderSearch, Plus, Search, SearchX, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { InvestigationStatus, Priority } from '@/domain/types'
import { useInvestigationContext } from '@/app/investigation-context'
import { ApiError } from '@/services/apiClient'
import { can } from '@/services/authService'
import { useCurrentUser, useInvestigations } from '@/services/queries'
import { PriorityBadge, StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { investigationStatusTerms, priorityTerms } from '@/design-system/vocabulary'
import { formatDateTime } from '@/lib/format'
import { NewInvestigationDialog } from './NewInvestigationDialog'

const PAGE_SIZE = 20
const ALL = 'all'

/**
 * Investigations list (plan §10). Filters live in the URL (?search=…&status=…&page=…),
 * so a filtered view can be bookmarked or shared, and the Back button works.
 */
export function InvestigationsPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const { data: user } = useCurrentUser()
  const setCurrentInvestigation = useInvestigationContext((s) => s.setCurrentInvestigation)
  const [creating, setCreating] = useState(false)

  const search = params.get('search') ?? ''
  const status = (params.get('status') as InvestigationStatus | null) ?? undefined
  const priority = (params.get('priority') as Priority | null) ?? undefined
  const page = Math.max(1, Number(params.get('page') ?? 1))

  // Always build on the *latest* URL (functional update), never on a stale copy.
  const update = useCallback(
    (changes: Record<string, string | null>) =>
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          for (const [key, value] of Object.entries(changes)) {
            if (value === null || value === ALL) next.delete(key)
            else next.set(key, value)
          }
          return next
        },
        { replace: true },
      ),
    [setParams],
  )

  // Typing updates the box instantly; the URL (and the request) follows 300 ms after the last key.
  const [searchText, setSearchText] = useState(search)
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const onSearchChange = (value: string) => {
    setSearchText(value)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => update({ search: value.trim() || null, page: null }), 300)
  }
  useEffect(() => () => clearTimeout(searchTimer.current), [])

  // Keep the box in step when the URL changes from outside (Back button, "Clear filters").
  const [syncedSearch, setSyncedSearch] = useState(search)
  if (search !== syncedSearch) {
    setSyncedSearch(search)
    setSearchText(search)
  }

  const clearFilters = () => {
    clearTimeout(searchTimer.current)
    setParams({}, { replace: true })
  }

  const query = { search: search || undefined, status, priority, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }
  const { data, isPending, isError, error, refetch, isFetching } = useInvestigations(query)
  const filtered = Boolean(search || status || priority)
  const canCreate = can(user, 'investigation:write')

  const open = (reference: string) => {
    setCurrentInvestigation(reference)
    navigate(`/investigations/${reference}`)
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Investigations"
        description="Cases you are on the team for. Supervisors see every case."
        actions={
          canCreate && (
            <Button onClick={() => setCreating(true)}>
              <Plus /> New investigation
            </Button>
          )
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchText}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search title, case ID, location…"
            aria-label="Search investigations"
            className="pl-8"
          />
        </div>
        <Select value={status ?? ALL} onValueChange={(v) => update({ status: v, page: null })}>
          <SelectTrigger className="w-40" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {Object.entries(investigationStatusTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}>{term.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={priority ?? ALL} onValueChange={(v) => update({ priority: v, page: null })}>
          <SelectTrigger className="w-40" aria-label="Filter by priority">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All priorities</SelectItem>
            {Object.entries(priorityTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}>{term.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {filtered && (
          <Button variant="ghost" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
      </div>

      {isError ? (
        <ErrorState
          description={error instanceof ApiError ? error.message : 'Investigations could not be loaded.'}
          onRetry={() => refetch()}
          retrying={isFetching}
        />
      ) : !isPending && data.total === 0 ? (
        filtered ? (
          <EmptyState
            icon={SearchX}
            title="No investigations match these filters"
            description="Try a different search term, or clear the filters."
            action={<Button variant="outline" onClick={clearFilters}>Clear filters</Button>}
          />
        ) : (
          <EmptyState
            icon={FolderSearch}
            title="No investigations yet"
            description="You are not on the team of any investigation. Create one, or ask a supervisor to add you."
            action={canCreate && <Button onClick={() => setCreating(true)}><Plus /> New investigation</Button>}
          />
        )
      ) : (
        <Card className="gap-0 py-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Case</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead className="hidden md:table-cell">Lead</TableHead>
                <TableHead className="hidden lg:table-cell">Team</TableHead>
                <TableHead className="hidden pr-4 lg:table-cell">Last updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className={isFetching && !isPending ? 'opacity-60 transition-opacity' : undefined}>
              {isPending
                ? Array.from({ length: 6 }, (_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={7} className="px-4">
                        <Skeleton className="h-8 w-full" />
                      </TableCell>
                    </TableRow>
                  ))
                : data.items.map((investigation) => (
                    <TableRow
                      key={investigation.reference}
                      className="cursor-pointer"
                      onClick={() => open(investigation.reference)}
                    >
                      <TableCell className="pl-4">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            open(investigation.reference)
                          }}
                          className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          aria-label={`Open ${investigation.reference}: ${investigation.title}`}
                        >
                          <IdTag>{investigation.reference}</IdTag>
                        </button>
                      </TableCell>
                      <TableCell className="max-w-80">
                        <p className="truncate font-medium">{investigation.title}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {investigation.caseType}
                          {investigation.location && ` · ${investigation.location}`}
                        </p>
                      </TableCell>
                      <TableCell>
                        <StatusBadge kind="investigation" status={investigation.status} />
                      </TableCell>
                      <TableCell>
                        <PriorityBadge priority={investigation.priority} />
                      </TableCell>
                      <TableCell className="hidden text-muted-foreground md:table-cell">
                        {investigation.leadInvestigator.displayName}
                      </TableCell>
                      <TableCell className="hidden text-muted-foreground lg:table-cell">
                        <span className="inline-flex items-center gap-1">
                          <Users aria-hidden className="size-3.5" /> {investigation.teamSize}
                        </span>
                      </TableCell>
                      <TableCell className="hidden pr-4 text-muted-foreground tabular-nums lg:table-cell">
                        {formatDateTime(investigation.updatedAt)}
                      </TableCell>
                    </TableRow>
                  ))}
            </TableBody>
          </Table>
          {data && data.total > 0 && (
            <Pagination
              page={page}
              total={data.total}
              onPage={(next) => update({ page: next === 1 ? null : String(next) })}
            />
          )}
        </Card>
      )}

      <NewInvestigationDialog open={creating} onOpenChange={setCreating} />
    </div>
  )
}

function Pagination({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const first = (page - 1) * PAGE_SIZE + 1
  const last = Math.min(page * PAGE_SIZE, total)
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between border-t px-4 py-2.5 text-sm">
      <p className="text-muted-foreground tabular-nums">
        {first}–{last} of {total}
      </p>
      <div className="flex items-center gap-1">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft /> Previous
        </Button>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next <ChevronRight />
        </Button>
      </div>
    </nav>
  )
}
