import { Link, useNavigate } from 'react-router'
import {
  Bell,
  BookOpen,
  CircleCheck,
  CircleHelp,
  CircleX,
  FileText,
  FolderSearch,
  Keyboard,
  ListChecks,
  LogOut,
  Monitor,
  Moon,
  Palette,
  Sun,
  TriangleAlert,
  Waypoints,
  type LucideIcon,
} from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Kbd } from '@/components/ui/kbd'
import { Skeleton } from '@/components/ui/skeleton'
import { useTheme, type ThemePreference } from '@/app/theme'
import type { NotificationKind } from '@/domain/types'
import { timeAgo } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useCurrentUser, useLogout, useMarkNotificationsRead, useNotifications } from '@/services/queries'
import { roleLabels } from '@/design-system/vocabulary'

const NOTIFICATION_ICONS: Record<NotificationKind, LucideIcon> = {
  processing_completed: CircleCheck,
  processing_failed: CircleX,
  requires_review: TriangleAlert,
  correlation_detected: Waypoints,
  task_assigned: ListChecks,
  investigation_assigned: FolderSearch,
  report_ready: FileText,
}

/** The bell: things that need *you*. Polled every 30 s; clicking one opens it and marks it read. */
export function NotificationsMenu() {
  const { data } = useNotifications()
  const markRead = useMarkNotificationsRead()
  const navigate = useNavigate()
  const unread = data?.unread ?? 0
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}>
          <Bell />
          {unread > 0 && (
            <span aria-hidden className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[0.6rem] font-semibold text-white tabular-nums">
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[22rem] max-w-[calc(100vw-1rem)]">
        <div className="flex items-center justify-between px-2 py-1.5">
          <DropdownMenuLabel className="p-0">Notifications</DropdownMenuLabel>
          {unread > 0 && (
            <Button variant="ghost" size="xs" onClick={(e) => { e.preventDefault(); markRead.mutate(null) }}>
              Mark all read
            </Button>
          )}
        </div>
        <DropdownMenuSeparator />
        {!data || data.items.length === 0 ? (
          <div className="space-y-1 px-2 py-6 text-center">
            <p className="text-sm font-medium">You're all caught up</p>
            <p className="text-xs text-muted-foreground">Processing results, review requests and tasks for you will appear here.</p>
          </div>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            {data.items.map((n) => {
              const Icon = NOTIFICATION_ICONS[n.kind] ?? Bell
              return (
                <DropdownMenuItem
                  key={n.id}
                  className="items-start gap-2.5 py-2"
                  onSelect={() => {
                    if (!n.read) markRead.mutate(n.id)
                    if (n.link) navigate(n.link)
                  }}
                >
                  <Icon aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 space-y-0.5">
                    <span className={cn('block text-sm', !n.read && 'font-semibold')}>{n.title}</span>
                    {n.body && <span className="line-clamp-2 block text-xs text-muted-foreground">{n.body}</span>}
                    <span className="block text-[0.7rem] text-muted-foreground">{timeAgo(n.createdAt)}</span>
                  </span>
                  {!n.read && <span aria-label="unread" className="mt-1.5 size-2 shrink-0 rounded-full bg-primary" />}
                </DropdownMenuItem>
              )
            })}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function HelpMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Help">
          <CircleHelp />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>Help</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled className="justify-between">
          <span className="flex items-center gap-2">
            <Keyboard /> Search
          </span>
          <Kbd>Ctrl K</Kbd>
        </DropdownMenuItem>
        <DropdownMenuItem disabled className="justify-between">
          <span className="flex items-center gap-2">
            <Keyboard /> Toggle sidebar
          </span>
          <Kbd>Ctrl B</Kbd>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/design-system">
            <Palette /> Design system
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <a href="https://github.com/kandiharish/Falcon" target="_blank" rel="noreferrer">
            <BookOpen /> Project documentation
          </a>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

const themeOptions: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

export function UserMenu() {
  const { data: user, isPending } = useCurrentUser()
  const { preference, setPreference } = useTheme()
  const logout = useLogout()
  const navigate = useNavigate()

  if (isPending || !user) return <Skeleton className="size-8 rounded-full" />

  const initials = user.displayName
    .split(/[\s.]+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-9 gap-2 px-1.5" aria-label="Account menu">
          <Avatar className="size-7">
            <AvatarFallback className="bg-primary/10 text-xs font-medium text-primary">
              {initials}
            </AvatarFallback>
          </Avatar>
          <span className="hidden text-left leading-tight lg:block">
            <span className="block text-sm">{user.displayName}</span>
            {/* Role indicator (plan §7) */}
            <span className="block text-[0.7rem] text-muted-foreground">{roleLabels[user.role]}</span>
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="space-y-0.5">
          <p className="text-sm font-medium text-foreground">{user.displayName}</p>
          <p className="text-xs font-normal">{user.email}</p>
          <p className="text-xs font-normal">Role: {roleLabels[user.role]}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Appearance</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={preference}
          onValueChange={(value) => setPreference(value as ThemePreference)}
        >
          {themeOptions.map(({ value, label, icon: Icon }) => (
            <DropdownMenuRadioItem key={value} value={value}>
              <Icon /> {label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={logout.isPending}
          onSelect={() => logout.mutate(undefined, { onSettled: () => navigate('/login') })}
        >
          <LogOut /> {logout.isPending ? 'Signing out…' : 'Sign out'}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
