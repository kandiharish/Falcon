/** Shown for the split second while the first page's code downloads. */
export function AppLoading() {
  return (
    <div role="status" className="flex min-h-svh items-center justify-center bg-background">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <span className="size-4 animate-spin rounded-full border-2 border-primary border-r-transparent" />
        Loading FALCON…
      </div>
    </div>
  )
}
