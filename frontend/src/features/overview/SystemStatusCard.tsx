import { CircleCheck, OctagonX, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/services/apiClient'
import { useSystemHealth } from '@/services/queries'
import { ErrorState } from '@/design-system/states'
import { cn } from '@/lib/utils'

/** The Phase 1 health check, now using TanStack Query (loading, caching, retry for free). */
export function SystemStatusCard() {
  const { data, isPending, isError, error, refetch, isFetching } = useSystemHealth()

  return (
    <Card>
      <CardHeader>
        <CardTitle>System status</CardTitle>
        <CardDescription>Browser → API → Database</CardDescription>
        <CardAction>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label="Re-run system check"
          >
            <RefreshCw className={cn(isFetching && 'animate-spin')} />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-5 w-full" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState
            title="System check failed"
            description={
              error instanceof ApiError ? error.message : 'The system check could not be completed.'
            }
            onRetry={() => refetch()}
            retrying={isFetching}
          />
        ) : (
          <ul className="divide-y text-sm">
            <StatusRow label="API" ok detail="Responding" />
            <StatusRow
              label="Database"
              ok={data.database.connected}
              detail={
                data.database.connected
                  ? `PostgreSQL ${data.database.server_version?.split(' ')[0]}`
                  : 'Not reachable'
              }
            />
            {Object.entries(data.database.extensions).map(([name, version]) => (
              <StatusRow key={name} label={name} ok={version !== null} detail={version ? `v${version}` : 'Missing'} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  const Icon = ok ? CircleCheck : OctagonX
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('flex items-center gap-1.5', ok ? 'text-success' : 'text-destructive')}>
        <Icon aria-hidden className="size-4" />
        <span className="text-foreground">{detail}</span>
        <span className="sr-only">{ok ? '(healthy)' : '(problem)'}</span>
      </span>
    </li>
  )
}
