/**
 * The FALCON information architecture (plan §7) in ONE place.
 * Sidebar, breadcrumbs, global search and "coming soon" pages all read from here.
 */
import {
  Activity,
  ChartGantt,
  FileStack,
  FileText,
  FolderSearch,
  LayoutDashboard,
  ListChecks,
  Microscope,
  Network,
  ScrollText,
  Settings,
  UserRoundSearch,
  Waypoints,
  type LucideIcon,
} from 'lucide-react'
import type { Permission } from '@/domain/types'

export interface NavItem {
  id: string
  label: string
  path: string
  icon: LucideIcon
  /** The roadmap phase that delivers this module. */
  phase: number
  /** Permission needed to see this module (none = every signed-in user). */
  permission?: Permission
  summary: string
  capabilities: string[]
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export const navigation: NavGroup[] = [
  {
    label: 'Command',
    items: [
      {
        id: 'overview',
        label: 'Overview',
        path: '/',
        icon: LayoutDashboard,
        phase: 2,
        summary: 'The investigation command center.',
        capabilities: [],
      },
      {
        id: 'investigations',
        permission: 'investigation:read',
        label: 'Investigations',
        path: '/investigations',
        icon: FolderSearch,
        phase: 4,
        summary: 'Create, search and manage investigations and their teams.',
        capabilities: [
          'Investigation list with search and filters',
          'Create investigation',
          'Investigation command center: evidence, entities, events, team, activity',
        ],
      },
    ],
  },
  {
    label: 'Evidence',
    items: [
      {
        id: 'evidence',
        permission: 'evidence:read',
        label: 'Evidence',
        path: '/evidence',
        icon: FileStack,
        phase: 5,
        summary: 'Upload, preserve and process evidence with integrity tracking.',
        capabilities: [
          'Upload with SHA-256 fingerprint; originals never modified',
          'Processing pipeline with live progress',
          'Evidence workspace: preview, metadata, extracted information, audit trail',
        ],
      },
      {
        id: 'entities',
        permission: 'evidence:read',
        label: 'Entities',
        path: '/entities',
        icon: UserRoundSearch,
        phase: 6,
        summary: 'People, devices, vehicles, accounts and locations found across evidence.',
        capabilities: [
          'Entity profiles with evidence references',
          'Provenance labels and confidence on every mention',
          'Relationship exploration from the profile',
        ],
      },
      {
        id: 'events',
        permission: 'evidence:read',
        label: 'Events',
        path: '/events',
        icon: Activity,
        phase: 6,
        summary: 'Things that happened: detections, calls, transactions, movements.',
        capabilities: [
          'Event list with time, location and involved entities',
          'Every event links to its source evidence',
        ],
      },
    ],
  },
  {
    label: 'Analysis',
    items: [
      {
        id: 'timeline',
        permission: 'evidence:read',
        label: 'Timeline',
        path: '/timeline',
        icon: ChartGantt,
        phase: 7,
        summary: 'Chronological view of events across all evidence sources, with a map.',
        capabilities: [
          'Zoom, grouping and filters by entity, location, source and type',
          'Map of evidence and event locations',
        ],
      },
      {
        id: 'correlations',
        permission: 'evidence:read',
        label: 'Correlations',
        path: '/correlations',
        icon: Waypoints,
        phase: 8,
        summary: 'Potential relationships between evidence, each with its reasons.',
        capabilities: [
          'Time, location, entity and cross-source correlation',
          '"Why this relationship exists" with supporting factors',
          'Analyst review: confirm or reject',
        ],
      },
      {
        id: 'graph',
        permission: 'evidence:read',
        label: 'Relationship Graph',
        path: '/graph',
        icon: Network,
        phase: 9,
        summary: 'Interactive network of entities, evidence and events.',
        capabilities: [
          'Zoom, pan, search and filter',
          'Select a link to see why it exists',
          'Drill down to evidence and timeline',
        ],
      },
      {
        id: 'analysis',
        permission: 'evidence:read',
        label: 'Analysis',
        path: '/analysis',
        icon: Microscope,
        phase: 10,
        summary: 'Analysis workspace with AI assistance and natural-language search.',
        capabilities: [
          'Natural-language investigation search',
          'Investigation Assistant (AI agent) — cites evidence, requires review',
          'Analyst notes',
        ],
      },
    ],
  },
  {
    label: 'Output',
    items: [
      {
        id: 'reports',
        permission: 'investigation:read',
        label: 'Reports',
        path: '/reports',
        icon: FileText,
        phase: 11,
        summary: 'Professional investigation reports separating evidence from interpretation.',
        capabilities: ['Report preview and printable view', 'Observed evidence vs analysis'],
      },
      {
        id: 'tasks',
        permission: 'investigation:read',
        label: 'Tasks',
        path: '/tasks',
        icon: ListChecks,
        phase: 11,
        summary: 'Investigation tasks assigned to the team.',
        capabilities: ['To Do → In Progress → Review → Completed', 'Linked to evidence'],
      },
    ],
  },
  {
    label: 'Governance',
    items: [
      {
        id: 'audit',
        permission: 'audit:read',
        label: 'Audit Logs',
        path: '/audit',
        icon: ScrollText,
        phase: 11,
        summary: 'Tamper-evident record of every sensitive action.',
        capabilities: ['Who did what, when, before/after state', 'Not editable by users'],
      },
      {
        id: 'admin',
        permission: 'users:read',
        label: 'Administration',
        path: '/admin',
        icon: Settings,
        phase: 3,
        summary: 'Users, roles, permissions and system settings.',
        capabilities: ['User management', 'Roles and permissions', 'Security and retention settings'],
      },
    ],
  },
]

/** Modules the current user may see. */
export function visibleNavigation(permissions: readonly Permission[]): NavGroup[] {
  return navigation
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !item.permission || permissions.includes(item.permission)),
    }))
    .filter((group) => group.items.length > 0)
}

export const allNavItems: NavItem[] = navigation.flatMap((group) => group.items)

export function findNavItem(pathname: string): NavItem | undefined {
  if (pathname === '/') return allNavItems[0]
  // An evidence item lives under its case (/investigations/CASE-…/evidence/IMG-001) but belongs to Evidence.
  if (/\/evidence(\/|$)/.test(pathname)) return allNavItems.find((item) => item.id === 'evidence')
  if (/\/reports(\/|$)/.test(pathname)) return allNavItems.find((item) => item.id === 'reports')
  if (/\/reports(\/|$)/.test(pathname)) return allNavItems.find((item) => item.id === 'reports')
  if (/\/correlations(\/|$)/.test(pathname)) return allNavItems.find((item) => item.id === 'correlations')
  if (/\/entities(\/|$)/.test(pathname)) return allNavItems.find((item) => item.id === 'entities')
  return allNavItems.find((item) => item.path !== '/' && pathname.startsWith(item.path))
}
