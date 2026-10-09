/**
 * The case page's working panels (plan §55): the strongest leads, FALCON's suggestions, the
 * incident replay, and the COURT PACK — certificates, labels and the bundle a prosecutor or
 * defence expert can verify without FALCON.
 */
import { Link } from 'react-router'
import { ArrowRight, FileArchive, Lightbulb, Play, QrCode, Scale, Waypoints } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { Investigation } from '@/domain/types'
import { can } from '@/services/authService'
import { DocumentsService } from '@/services/documentsService'
import { useCorrelations, useCurrentUser, useEvidenceList } from '@/services/queries'
import { IdTag } from '@/design-system/IdTag'
import { LevelBadge } from '@/features/correlations/components'
import { InsightsPanel } from '@/features/insights/InsightsPanel'

export function SuggestionsCard({ investigation }: { investigation: Investigation }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Lightbulb aria-hidden className="size-4 text-warning" /> FALCON suggests</CardTitle>
        <CardDescription>What this case's records say to check next, and the request that would answer it.</CardDescription>
      </CardHeader>
      <CardContent><InsightsPanel caseRef={investigation.reference} /></CardContent>
    </Card>
  )
}

export function KeyLeadsCard({ investigation }: { investigation: Investigation }) {
  const { data, isPending } = useCorrelations(investigation.reference, {})
  const top = (data?.items ?? []).slice(0, 4)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Waypoints aria-hidden className="size-4 text-primary" /> Strongest leads</CardTitle>
        <CardDescription>Potential relationships, not proof.</CardDescription>
        <CardAction>
          <Button asChild variant="ghost" size="sm"><Link to="/correlations">All <ArrowRight /></Link></Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isPending ? <Skeleton className="h-32 w-full" /> : top.length === 0 ? (
          <p className="text-sm text-muted-foreground">No relationships yet. They appear as evidence is processed.</p>
        ) : (
          <ul className="divide-y">
            {top.map((c) => (
              <li key={c.reference}>
                <Link to={`/investigations/${investigation.reference}/correlations/${c.reference}`}
                  className="flex items-center gap-2 py-2 text-sm outline-none hover:text-primary focus-visible:ring-2 focus-visible:ring-ring">
                  <IdTag>{c.reference}</IdTag>
                  <span className="min-w-0 flex-1 truncate">{c.evidenceA.reference} ⟷ {c.evidenceB.reference}</span>
                  <LevelBadge level={c.level} score={c.score} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function ReplayCard() {
  return (
    <Card className="overflow-hidden bg-gradient-to-br from-primary/10 to-transparent">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Play aria-hidden className="size-4 text-primary" /> Replay the incident</CardTitle>
        <CardDescription>Watch every located record appear on the map, minute by minute, with a clock.</CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild><Link to="/timeline?view=replay"><Play /> Start replay</Link></Button>
      </CardContent>
    </Card>
  )
}

export function CourtPackCard({ investigation }: { investigation: Investigation }) {
  const { data: user } = useCurrentUser()
  const onTeam = investigation.myRoleInCase !== null || user?.role === 'supervisor'
  const canExport = can(user, 'report:generate') && onTeam
  const { data } = useEvidenceList(investigation.reference, { limit: 100 })
  const items = data?.items ?? []
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Scale aria-hidden className="size-4 text-primary" /> Court pack</CardTitle>
        <CardDescription>Drafts and exports for court. Every one is recorded in the audit log.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {canExport && (
            <Button asChild size="sm">
              {/* A real link: the browser downloads the ZIP; the server records the export. */}
              <a href={DocumentsService.bundleUrl(investigation.reference)}><FileArchive /> Court bundle (.zip)</a>
            </Button>
          )}
          {onTeam && (
            <Button asChild size="sm" variant="outline">
              <Link to={`/investigations/${investigation.reference}/labels`}><QrCode /> Evidence labels</Link>
            </Button>
          )}
        </div>
        {onTeam && items.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Section 63 certificates (BSA 2023), drafts</p>
            <div className="flex flex-wrap gap-1.5">
              {items.map((e) => (
                <Link key={e.reference} to={`/investigations/${investigation.reference}/evidence/${e.reference}/certificate`}
                  className="rounded outline-none hover:opacity-80 focus-visible:ring-2 focus-visible:ring-ring" aria-label={`Section 63 certificate for ${e.reference}`}>
                  <IdTag>{e.reference}</IdTag>
                </Link>
              ))}
            </div>
          </div>
        )}
        {canExport && (
          <p className="text-xs text-muted-foreground">
            The bundle holds the originals, their SHA-256 fingerprints (check with <code className="font-mono">sha256sum -c</code>),
            draft certificates, the timeline, the leads and the audit trail.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
