import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { FolderSearch, Search, SearchX, UserRoundSearch } from 'lucide-react'
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
import type { EntityType, ReviewStatus } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useEntities } from '@/services/queries'
import { AssertionLabel, StatusBadge } from '@/design-system/badges'
import { ConfidenceIndicator } from '@/design-system/ConfidenceIndicator'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { entityTypeTerms, reviewStatusTerms } from '@/design-system/vocabulary'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { useCurrentCase } from './useCaseAccess'

const ALL = 'all'

/** Entity intelligence (plan §15): every person, phone, device, vehicle … found in the case. */
export function EntitiesPage() {
  const caseRef = useCurrentCase()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [type, setType] = useState<EntityType | typeof ALL>(ALL)
  const [review, setReview] = useState<ReviewStatus | typeof ALL>(ALL)
  const debounced = useDebouncedValue(search)
  const query = {
    search: debounced.trim() || undefined,
    entity_type: type === ALL ? undefined : type,
    review_status: review === ALL ? undefined : review,
  }
  const { data, isPending, isError, error, refetch, isFetching } = useEntities(caseRef, query)

  if (!caseRef) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState
          icon={FolderSearch}
          title="No investigation selected"
          description="Entities belong to an investigation. Choose one in the top bar."
          action={<Button asChild variant="outline"><Link to="/investigations">Open investigations</Link></Button>}
        />
      </div>
    )
  }
  const filtered = Boolean(query.search || query.entity_type || query.review_status)

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        eyebrow={<IdTag>{caseRef}</IdTag>}
        title="Entities"
        description="People, phones, devices, vehicles, accounts and places found across the evidence. The same identifier in several files is one entity."
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, number, ID…" aria-label="Search entities" className="pl-8" />
        </div>
        <Select value={type} onValueChange={(v) => setType(v as EntityType | typeof ALL)}>
          <SelectTrigger className="w-44" aria-label="Filter by type"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All types</SelectItem>
            {Object.entries(entityTypeTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}><term.icon /> {term.plural}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={review} onValueChange={(v) => setReview(v as ReviewStatus | typeof ALL)}>
          <SelectTrigger className="w-44" aria-label="Filter by review"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Any review status</SelectItem>
            {Object.entries(reviewStatusTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}>{term.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isError ? (
        <ErrorState description={error instanceof ApiError ? error.message : 'Entities could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
      ) : !isPending && data.total === 0 ? (
        filtered ? (
          <EmptyState icon={SearchX} title="No entities match these filters" description="Try a different search or filter." />
        ) : (
          <EmptyState icon={UserRoundSearch} title="No entities yet" description="Entities appear automatically when evidence is processed, or when analysts add them." />
        )
      ) : (
        <Card className="gap-0 py-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Entity</TableHead>
                <TableHead>Name / identifier</TableHead>
                <TableHead className="text-right">Evidence</TableHead>
                <TableHead className="hidden text-right md:table-cell">Events</TableHead>
                <TableHead className="hidden lg:table-cell">How found</TableHead>
                <TableHead className="hidden lg:table-cell">Confidence</TableHead>
                <TableHead className="pr-4">Review</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isPending
                ? Array.from({ length: 6 }, (_, i) => (
                    <TableRow key={i}><TableCell colSpan={7} className="px-4"><Skeleton className="h-7 w-full" /></TableCell></TableRow>
                  ))
                : data.items.map((entity) => {
                    const term = entityTypeTerms[entity.entityType]
                    const open = () => navigate(`/investigations/${caseRef}/entities/${entity.reference}`)
                    return (
                      <TableRow key={entity.reference} className="cursor-pointer" onClick={open}>
                        <TableCell className="pl-4">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              open()
                            }}
                            aria-label={`Open ${entity.reference}`}
                            className="inline-flex items-center gap-1.5 rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <term.icon aria-hidden className="size-4 text-muted-foreground" />
                            <IdTag>{entity.reference}</IdTag>
                          </button>
                        </TableCell>
                        <TableCell>
                          <p className="font-medium">{entity.label}</p>
                          <p className="text-xs text-muted-foreground">{term.label}</p>
                        </TableCell>
                        <TableCell className="text-right font-mono tabular-nums">{entity.evidenceCount}</TableCell>
                        <TableCell className="hidden text-right font-mono tabular-nums md:table-cell">{entity.eventCount}</TableCell>
                        <TableCell className="hidden lg:table-cell">
                          <div className="flex flex-wrap gap-1">
                            {entity.assertionKinds.map((kind) => <AssertionLabel key={kind} kind={kind} />)}
                          </div>
                        </TableCell>
                        <TableCell className="hidden lg:table-cell">
                          {entity.maxConfidence !== null && <ConfidenceIndicator score={entity.maxConfidence} />}
                        </TableCell>
                        <TableCell className="pr-4">
                          <StatusBadge kind="review" status={entity.reviewStatus} />
                        </TableCell>
                      </TableRow>
                    )
                  })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  )
}
