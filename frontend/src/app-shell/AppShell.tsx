import { Link, Outlet, useLocation } from 'react-router'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { findNavItem } from '@/app/navigation'
import { AppSidebar } from './AppSidebar'
import { GlobalSearch } from './GlobalSearch'
import { InvestigationContextBar } from './InvestigationContextBar'
import { InvestigationSwitcher } from './InvestigationSwitcher'
import { HelpMenu, NotificationsMenu, UserMenu } from './TopBarMenus'
import { useValidCurrentInvestigation } from './useValidCurrentInvestigation'

/**
 * The frame around every page:
 *   sidebar | top bar (search, investigation, notifications, help, user)
 *           | investigation context strip
 *           | page content (<Outlet />)
 */
export function AppShell() {
  const { pathname } = useLocation()
  const current = findNavItem(pathname)
  const pageLabel =
    pathname === '/design-system' ? 'Design system' : pathname === '/account/security' ? 'Account security' : (current?.label ?? 'Not found')
  useValidCurrentInvestigation()

  return (
    <SidebarProvider>
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <AppSidebar />
      <SidebarInset>
        <header data-print="hide" className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-3 backdrop-blur lg:px-4">
          <SidebarTrigger aria-label="Toggle navigation" />
          <Separator orientation="vertical" className="mr-1 h-5!" />
          <Breadcrumb className="hidden md:block">
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link to="/">FALCON</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>{pageLabel}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
          <div className="flex min-w-0 flex-1 justify-end px-2 sm:justify-center">
            <GlobalSearch />
          </div>
          <div className="flex items-center gap-1">
            <div className="hidden sm:block">
              <InvestigationSwitcher />
            </div>
            <NotificationsMenu />
            <div className="hidden sm:block">
              <HelpMenu />
            </div>
            <UserMenu />
          </div>
        </header>
        <InvestigationContextBar />
        <div id="main" tabIndex={-1} className="flex-1 px-4 py-6 outline-none lg:px-6">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
