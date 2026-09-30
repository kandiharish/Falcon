import { Link, useNavigate } from 'react-router'
import { Bell, BookOpen, CircleHelp, Keyboard, LogOut, Monitor, Moon, Palette, Sun } from 'lucide-react'
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
import { useCurrentUser, useLogout } from '@/services/queries'
import { roleLabels } from '@/design-system/vocabulary'

export function NotificationsMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Notifications</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="space-y-1 px-2 py-6 text-center">
          <p className="text-sm font-medium">You're all caught up</p>
          <p className="text-xs text-muted-foreground">
            Processing results, review requests and task reminders will appear here.
          </p>
        </div>
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
