import type { ReactNode } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router'
import { AppLoading } from '@/app-shell/AppLoading'
import { AppShell } from '@/app-shell/AppShell'
import { RouteError } from '@/app-shell/RouteError'
import { RequireAuth, RequirePermission } from './auth'
import { allNavItems, type NavItem } from './navigation'

/**
 *  /login                       public
 *  / (RequireAuth)              must be signed in
 *    └─ AppShell                sidebar + top bar
 *         ├─ index              overview
 *         ├─ admin              users:read
 *         └─ other modules      their own permission ("planned" pages until built)
 *
 * Pages are lazy-loaded: each page's code downloads only when first opened (plan §39).
 */

const guard = (item: NavItem, page: ReactNode) =>
  item.permission ? <RequirePermission permission={item.permission}>{page}</RequirePermission> : page

const builtPages: Record<string, RouteObject['lazy']> = {
  admin: async () => {
    const { UsersPage } = await import('@/features/admin/UsersPage')
    const item = allNavItems.find((i) => i.id === 'admin')!
    return { Component: () => guard(item, <UsersPage />) }
  },
}

const moduleRoutes: RouteObject[] = allNavItems
  .filter((item) => item.path !== '/')
  .map((item) => ({
    path: item.path.slice(1),
    lazy:
      builtPages[item.id] ??
      (async () => {
        const { UpcomingModulePage } = await import('@/features/upcoming/UpcomingModulePage')
        return { Component: () => guard(item, <UpcomingModulePage item={item} />) }
      }),
  }))

export const router = createBrowserRouter([
  {
    path: '/login',
    errorElement: <RouteError />,
    hydrateFallbackElement: <AppLoading />,
    lazy: async () => ({ Component: (await import('@/features/auth/LoginPage')).LoginPage }),
  },
  {
    path: '/',
    element: <RequireAuth />,
    errorElement: <RouteError />,
    hydrateFallbackElement: <AppLoading />,
    children: [
      {
        element: <AppShell />,
        children: [
          {
            index: true,
            lazy: async () => ({
              Component: (await import('@/features/overview/OverviewPage')).OverviewPage,
            }),
          },
          ...moduleRoutes,
          {
            path: 'design-system',
            lazy: async () => ({
              Component: (await import('@/features/design-system/DesignSystemPage')).DesignSystemPage,
            }),
          },
          {
            path: '*',
            lazy: async () => ({
              Component: (await import('@/features/not-found/NotFoundPage')).NotFoundPage,
            }),
          },
        ],
      },
    ],
  },
])
