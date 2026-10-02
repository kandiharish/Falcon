import { NavLink, useLocation } from 'react-router'
import { Palette } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'
import { findNavItem, visibleNavigation } from '@/app/navigation'
import { useCurrentUser } from '@/services/queries'
import { FalconMark } from './FalconMark'

const CURRENT_PHASE = 8

export function AppSidebar() {
  const { pathname } = useLocation()
  const active = findNavItem(pathname)
  const { data: user } = useCurrentUser()
  const groups = visibleNavigation(user?.permissions ?? [])

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2.5 px-1 py-1.5">
          <FalconMark className="size-8 shrink-0" />
          <div className="min-w-0 group-data-[collapsible=icon]:hidden">
            <p className="text-sm font-semibold tracking-[0.2em] text-sidebar-accent-foreground">
              FALCON
            </p>
            <p className="truncate text-[0.65rem] text-sidebar-foreground/70">
              Linked Crime Observation Network
            </p>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        {groups.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => {
                const Icon = item.icon
                const upcoming = item.phase > CURRENT_PHASE
                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton asChild isActive={active?.id === item.id} tooltip={item.label}>
                      <NavLink to={item.path} end={item.path === '/'}>
                        <Icon />
                        <span>{item.label}</span>
                      </NavLink>
                    </SidebarMenuButton>
                    {upcoming && (
                      <SidebarMenuBadge
                        className="text-[0.6rem] text-sidebar-foreground/50"
                        aria-label={`Arrives in phase ${item.phase}`}
                      >
                        P{item.phase}
                      </SidebarMenuBadge>
                    )}
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild isActive={pathname === '/design-system'} tooltip="Design system">
              <NavLink to="/design-system">
                <Palette />
                <span>Design system</span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
