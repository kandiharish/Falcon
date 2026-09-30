import { createBrowserRouter } from 'react-router'
import { AppLoading } from '@/app-shell/AppLoading'
import { AppShell } from '@/app-shell/AppShell'
import { RouteError } from '@/app-shell/RouteError'
import { allNavItems } from './navigation'

/**
 * Pages are lazy-loaded: each page's code downloads only when it is first opened (plan §39).
 * The shell (sidebar + top bar) loads once and stays.
 */
const upcomingRoutes = allNavItems
  .filter((item) => item.path !== '/')
  .map((item) => ({
    path: item.path.slice(1),
    lazy: async () => {
      const { UpcomingModulePage } = await import('@/features/upcoming/UpcomingModulePage')
      return { Component: () => <UpcomingModulePage item={item} /> }
    },
  }))

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    hydrateFallbackElement: <AppLoading />,
    errorElement: <RouteError />,
    children: [
      {
        index: true,
        lazy: async () => ({
          Component: (await import('@/features/overview/OverviewPage')).OverviewPage,
        }),
      },
      ...upcomingRoutes,
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
])
