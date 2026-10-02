import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { FileStack, FolderSearch, Plus, Search, SearchX } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
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
import type { Evidence, EvidenceStatus, EvidenceType } from '@/domain/types'
import { useInvestigationContext } from '@/app/investigation-context'
import { ApiError } from '@/services/apiClient'
import { can } from '@/services/authService'
import { isProcessing } from '@/services/evidenceService'
import { useCurrentUser, useEvidenceList, useInvestigation } from '@/services/queries'
import { StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { evidenceStatusTerms, evidenceTypeTerms } from '@/design-system/vocabulary'
import { formatBytes, formatDateTime } from '@/lib/format'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { UploadEvidenceDialog } from './UploadEvidenceDialog'

const ALL = 'all'

/** Evidence list for the current investigation (plan §11). */
export function EvidencePage() {
  const caseRef = useInvestigationContext((s) => s.currentInvestigationId)
  const { data: user } = useCurrentUser()
  const { data: investigation } = useInvestigation(caseRef)
  const navigate = useNavigate()
  const [uploading, setUploading] = useState(false)
  const [search, setSearch] = useState('')
  const [type, setType] = useState<EvidenceType | typeof ALL>(ALL)
  const [status, setStatus] = useState<EvidenceStatus | typeof ALL>(ALL)

  const debouncedSearch = useDebouncedValue(search)
  const query = {
    search: debouncedSearch.trim() || undefined,
    evidence_type: type === ALL ? undefined : type,
    status: status === ALL ? undefined : status,
    limit: 100,
  }
  const { data, isPending, isError, error, refetch, isFetching } = useEvidenceList(caseRef, query)

  const canUpload =
    can(user, 'evidence:upload') &&
    investigation?.myRoleInCase != null &&
    investigation.status !== 'closed' &&
    investigation.status !== 'archived'
  const filtered = Boolean(query.search || query.evidence_type || query.status)

  if (!caseRef) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState
          icon={FolderSearch}
          title="No investigation selected"
          description="Evidence belongs to an investigation. Choose one in the top bar or open the investigations list."
          action={<Button asChild variant="outline"><Link to="/investigations">Open investigations</Link></Button>}
        />
      </div>
    )
  }

  const open = (evidence: Evidence) => navigate(`/investigations/${caseRef}/evidence/${evidence.reference}`)

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        eyebrow={<IdTag>{caseRef}</IdTag>}
        title="Evidence"
        description="Every item is fingerprinted at upload and its original is never modified."
        actions={canUpload && <Button onClick={() => setUploading(true)}><Plus /> Add evidence</Button>}
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ID, file, source…"
            aria-label="Search evidence"
            className="pl-8"
          />
        </div>
        <Select value={type} onValueChange={(v) => setType(v as EvidenceType | typeof ALL)}>
          <SelectTrigger className="w-48" aria-label="Filter by type"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All types</SelectItem>
            {Object.entries(evidenceTypeTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}>{term.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={(v) => setStatus(v as EvidenceStatus | typeof ALL)}>
          <SelectTrigger className="w-44" aria-label="Filter by status"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {Object.entries(evidenceStatusTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}>{term.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isError ? (
        <ErrorState
          description={error instanceof ApiError ? error.message : 'Evidence could not be loaded.'}
          onRetry={() => refetch()}
          retrying={isFetching}
        />
      ) : !isPending && data.total === 0 ? (
        filtered ? (
          <EmptyState icon={SearchX} title="No evidence matches these filters" description="Try a different search or filter." />
        ) : (
          <EmptyState
            icon={FileStack}
            title="No evidence yet"
            description="No evidence has been added to this investigation yet."
            action={canUpload && <Button onClick={() => setUploading(true)}><Plus /> Add evidence</Button>}
          />
        )
      ) : (
        <Card className="gap-0 py-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Evidence</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden lg:table-cell">Collected</TableHead>
                <TableHead className="hidden pr-4 md:table-cell">Size</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isPending
                ? Array.from({ length: 5 }, (_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={6} className="px-4"><Skeleton className="h-8 w-full" /></TableCell>
                    </TableRow>
                  ))
                : data.items.map((evidence) => {
                    const term = evidenceTypeTerms[evidence.evidenceType]
                    return (
                      <TableRow key={evidence.reference} className="cursor-pointer" onClick={() => open(evidence)}>
                        <TableCell className="pl-4">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              open(evidence)
                            }}
                            aria-label={`Open ${evidence.reference}`}
                            className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <IdTag>{evidence.reference}</IdTag>
                          </button>
                        </TableCell>
                        <TableCell>
                          <span className="inline-flex items-center gap-1.5 text-sm whitespace-nowrap">
                            <term.icon aria-hidden className="size-4 text-muted-foreground" /> {term.label}
                          </span>
                        </TableCell>
                        <TableCell className="max-w-80">
                          <p className="truncate font-medium">{evidence.description || evidence.source || evidence.originalFilename}</p>
                          <p className="truncate font-mono text-xs text-muted-foreground">{evidence.originalFilename}</p>
                        </TableCell>
                        <TableCell className="min-w-36">
                          {isProcessing(evidence) ? (
                            <div className="space-y-1" aria-label={`Processing ${evidence.latestJob?.progress ?? 0}%`}>
                              <p className="text-xs">{evidence.latestJob?.currentStep ?? 'Queued'}</p>
                              <Progress value={evidence.latestJob?.progress ?? 0} className="h-1.5" />
                            </div>
                          ) : (
                            <StatusBadge kind="evidence" status={evidence.status} />
                          )}
                        </TableCell>
                        <TableCell className="hidden text-muted-foreground tabular-nums lg:table-cell">
                          {evidence.collectedAt ? formatDateTime(evidence.collectedAt) : '—'}
                        </TableCell>
                        <TableCell className="hidden pr-4 text-muted-foreground tabular-nums md:table-cell">
                          {formatBytes(evidence.sizeBytes)}
                        </TableCell>
                      </TableRow>
                    )
                  })}
            </TableBody>
          </Table>
        </Card>
      )}

      <UploadEvidenceDialog caseReference={caseRef} open={uploading} onOpenChange={setUploading} />
    </div>
  )
}
