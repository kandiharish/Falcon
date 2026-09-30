import { OctagonX } from 'lucide-react'
import { useRouteError } from 'react-router'
import { Button } from '@/components/ui/button'

/**
 * Shown when a screen crashes. Human-readable, with a recovery action (plan §38).
 * Technical details go to the console for developers, never to the user.
 */
export function RouteError() {
  const error = useRouteError()
  console.error('Screen failed to render:', error)

  return (
    <div role="alert" className="flex min-h-[60svh] items-center justify-center p-6">
      <div className="max-w-md space-y-4 text-center">
        <div className="mx-auto flex size-11 items-center justify-center rounded-full bg-destructive/10">
          <OctagonX aria-hidden className="size-5 text-destructive" />
        </div>
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">This screen could not be displayed</h1>
          <p className="text-sm text-muted-foreground">
            An unexpected problem stopped this page from loading. Your data has not been changed.
            Reload the page to try again.
          </p>
        </div>
        <div className="flex justify-center gap-2">
          <Button onClick={() => window.location.reload()}>Reload page</Button>
          <Button variant="outline" onClick={() => window.location.assign('/')}>
            Go to overview
          </Button>
        </div>
      </div>
    </div>
  )
}
