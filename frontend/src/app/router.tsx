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
 *         ├─ investigations     investigation:read (list + /investigations/:reference)
 *         ├─ evidence           evidence:read (list + /investigations/:ref/evidence/:evidenceRef)
 *         ├─ admin              users:read
 *         └─ other modules      their own permission ("planned" pages until built)
 *
 * Pages are lazy-loaded: each page's code downloads only when first opened (plan §39).
 */

const guard = (item: NavItem, page: ReactNode) =>
  item.permission ? <RequirePermission permission={item.permission}>{page}</RequirePermission> : page

const navItem = (id: string) => allNavItems.find((i) => i.id === id)!

const builtPages: Record<string, RouteObject['lazy']> = {
  investigations: async () => {
    const { InvestigationsPage } = await import('@/features/investigations/InvestigationsPage')
    return { Component: () => guard(navItem('investigations'), <InvestigationsPage />) }
  },
  evidence: async () => {
    const { EvidencePage } = await import('@/features/evidence/EvidencePage')
    return { Component: () => guard(navItem('evidence'), <EvidencePage />) }
  },
  entities: async () => {
    const { EntitiesPage } = await import('@/features/extraction/EntitiesPage')
    return { Component: () => guard(navItem('entities'), <EntitiesPage />) }
  },
  events: async () => {
    const { EventsPage } = await import('@/features/extraction/EventsPage')
    return { Component: () => guard(navItem('events'), <EventsPage />) }
  },
  timeline: async () => {
    const { TimelinePage } = await import('@/features/timeline/TimelinePage')
    return { Component: () => guard(navItem('timeline'), <TimelinePage />) }
  },
  correlations: async () => {
    const { CorrelationsPage } = await import('@/features/correlations/CorrelationsPage')
    return { Component: () => guard(navItem('correlations'), <CorrelationsPage />) }
  },
  graph: async () => {
    const { GraphPage } = await import('@/features/graph/GraphPage')
    return { Component: () => guard(navItem('graph'), <GraphPage />) }
  },
  analysis: async () => {
    const { AnalysisPage } = await import('@/features/analysis/AnalysisPage')
    return { Component: () => guard(navItem('analysis'), <AnalysisPage />) }
  },
  tasks: async () => {
    const { TasksPage } = await import('@/features/tasks/TasksPage')
    return { Component: () => guard(navItem('tasks'), <TasksPage />) }
  },
  reports: async () => {
    const { ReportsPage } = await import('@/features/reports/ReportsPage')
    return { Component: () => guard(navItem('reports'), <ReportsPage />) }
  },
  audit: async () => {
    const { AuditPage } = await import('@/features/audit/AuditPage')
    return { Component: () => guard(navItem('audit'), <AuditPage />) }
  },
  admin: async () => {
    const { UsersPage } = await import('@/features/admin/UsersPage')
    return { Component: () => guard(navItem('admin'), <UsersPage />) }
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
            path: 'investigations/:reference',
            lazy: async () => {
              const { InvestigationDetailPage } = await import(
                '@/features/investigations/InvestigationDetailPage'
              )
              return { Component: () => guard(navItem('investigations'), <InvestigationDetailPage />) }
            },
          },
          {
            path: 'investigations/:reference/evidence/:evidenceRef',
            lazy: async () => {
              const { EvidenceDetailPage } = await import('@/features/evidence/EvidenceDetailPage')
              return { Component: () => guard(navItem('evidence'), <EvidenceDetailPage />) }
            },
          },
          {
            path: 'investigations/:reference/entities/:entityRef',
            lazy: async () => {
              const { EntityDetailPage } = await import('@/features/extraction/EntityDetailPage')
              return { Component: () => guard(navItem('entities'), <EntityDetailPage />) }
            },
          },
          {
            path: 'investigations/:reference/evidence/:evidenceRef/certificate',
            lazy: async () => {
              const { CertificatePage } = await import('@/features/documents/DocumentPages')
              return { Component: () => guard(navItem('evidence'), <CertificatePage />) }
            },
          },
          {
            path: 'investigations/:reference/letters/:kind',
            lazy: async () => {
              const { LetterPage } = await import('@/features/documents/DocumentPages')
              return { Component: () => guard(navItem('evidence'), <LetterPage />) }
            },
          },
          {
            path: 'investigations/:reference/labels',
            lazy: async () => {
              const { LabelsPage } = await import('@/features/documents/LabelsPage')
              return { Component: () => guard(navItem('evidence'), <LabelsPage />) }
            },
          },
          {
            path: 'investigations/:reference/correlations/:correlationRef',
            lazy: async () => {
              const { CorrelationDetailPage } = await import('@/features/correlations/CorrelationDetailPage')
              return { Component: () => guard(navItem('correlations'), <CorrelationDetailPage />) }
            },
          },
          {
            path: 'investigations/:reference/reports/:reportRef',
            lazy: async () => {
              const { ReportDetailPage } = await import('@/features/reports/ReportDetailPage')
              return { Component: () => guard(navItem('reports'), <ReportDetailPage />) }
            },
          },
          {
            path: 'account/security',
            lazy: async () => ({ Component: (await import('@/features/account/SecurityPage')).SecurityPage }),
          },
          // A developer tool: production builds leave it out (it falls through to "not found").
          ...(import.meta.env.DEV
            ? [
                {
                  path: 'design-system',
                  lazy: async () => ({
                    Component: (await import('@/features/design-system/DesignSystemPage')).DesignSystemPage,
                  }),
                },
              ]
            : []),
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
