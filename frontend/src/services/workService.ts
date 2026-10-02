/**
 * WorkService (plan §29–§30): investigation tasks and the user's notifications.
 */
import type { NotificationDto, NotificationPageDto, TaskDto } from '@/api/types'
import type { AppNotification, NotificationKind, Priority, Task, TaskStatus } from '@/domain/types'
import { apiGet, apiPatch, apiPost } from './apiClient'

export interface TaskInput {
  title?: string
  description?: string
  status?: TaskStatus
  priority?: Priority
  assignee_id?: string | null
  due_date?: string | null
  evidence?: string[]
}

export const toTask = (dto: TaskDto): Task => ({
  reference: dto.reference,
  investigationReference: dto.investigation_reference,
  investigationTitle: dto.investigation_title,
  title: dto.title,
  description: dto.description,
  status: dto.status,
  priority: dto.priority,
  assignee: dto.assignee ? { id: dto.assignee.id, displayName: dto.assignee.display_name } : null,
  dueDate: dto.due_date ?? null,
  evidence: dto.evidence,
  createdBy: { id: dto.created_by.id, displayName: dto.created_by.display_name },
  createdAt: dto.created_at,
  updatedAt: dto.updated_at,
  completedAt: dto.completed_at ?? null,
})

const toNotification = (dto: NotificationDto): AppNotification => ({
  id: dto.id,
  kind: dto.kind as NotificationKind,
  title: dto.title,
  body: dto.body,
  link: dto.link,
  createdAt: dto.created_at,
  read: dto.read,
})

const tasksPath = (caseRef: string) => `/investigations/${encodeURIComponent(caseRef)}/tasks`

export const WorkService = {
  async tasks(caseRef: string): Promise<Task[]> {
    return (await apiGet<TaskDto[]>(tasksPath(caseRef))).map(toTask)
  },
  async myTasks(): Promise<Task[]> {
    return (await apiGet<TaskDto[]>('/tasks/mine')).map(toTask)
  },
  async createTask(caseRef: string, input: TaskInput): Promise<Task> {
    return toTask(await apiPost<TaskDto>(tasksPath(caseRef), input))
  },
  async updateTask(caseRef: string, reference: string, input: TaskInput): Promise<Task> {
    return toTask(await apiPatch<TaskDto>(`${tasksPath(caseRef)}/${encodeURIComponent(reference)}`, input))
  },
  async notifications(): Promise<{ items: AppNotification[]; unread: number }> {
    const page = await apiGet<NotificationPageDto>('/notifications')
    return { items: page.items.map(toNotification), unread: page.unread }
  },
  markRead: (id: string) => apiPost<void>(`/notifications/${id}/read`),
  markAllRead: () => apiPost<void>('/notifications/read-all'),
}
