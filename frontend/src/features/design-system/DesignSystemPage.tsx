import type { ReactNode } from 'react'
import { FileStack, Plus, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type {
  AssertionKind,
  EvidenceStatus,
  InvestigationStatus,
  Priority,
  ReviewStatus,
  TaskStatus,
} from '@/domain/types'
import { AssertionLabel, PriorityBadge, StatusBadge } from '@/design-system/badges'
import { ConfidenceIndicator } from '@/design-system/ConfidenceIndicator'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { ProcessingProgress } from '@/design-system/ProcessingProgress'
import { EmptyState, ErrorState } from '@/design-system/states'
import { WorkflowStepper } from '@/design-system/WorkflowStepper'

const colorTokens = [
  'background', 'foreground', 'card', 'primary', 'secondary', 'muted', 'accent', 'border',
  'destructive', 'success', 'warning', 'info', 'signal', 'inferred', 'sidebar', 'sidebar-primary',
]

const investigationStatuses: InvestigationStatus[] = ['draft', 'active', 'under_review', 'suspended', 'closed', 'archived']
const evidenceStatuses: EvidenceStatus[] = ['uploaded', 'processing', 'processed', 'verified', 'requires_review', 'archived']
const reviewStatuses: ReviewStatus[] = ['pending', 'confirmed', 'rejected']
const taskStatuses: TaskStatus[] = ['todo', 'in_progress', 'review', 'completed']
const priorities: Priority[] = ['low', 'medium', 'high', 'critical']
const assertionKinds: AssertionKind[] = ['fact', 'extracted', 'detected', 'correlated', 'inferred', 'user_entered']

export function DesignSystemPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-10">
      <PageHeader
        title="Design system"
        description="Every FALCON component and state in one place. Screens are built only from these parts."
      />

      <Section title="Colour tokens" note="Defined once in index.css; switch the theme from the user menu to see dark values.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {colorTokens.map((token) => (
            <div key={token} className="space-y-1.5">
              <div className="h-12 rounded-md border" style={{ background: `var(--${token})` }} />
              <p className="font-mono text-[0.7rem] text-muted-foreground">--{token}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Typography">
        <div className="space-y-2">
          <p className="text-2xl font-semibold tracking-tight">Heading · Investigation overview</p>
          <p className="text-lg font-semibold">Section · Correlation findings</p>
          <p className="text-sm">Body · Evidence collected at Riverside Industrial Zone, 29 Sept 2026.</p>
          <p className="text-xs text-muted-foreground">Label · Last updated by A. Kumar</p>
          <p className="font-mono text-sm">Mono · CCTV-001 · sha256 9f2c…a41e</p>
        </div>
      </Section>

      <Section title="Buttons" note="Hover, press and Tab-focus them to see each state.">
        <div className="flex flex-wrap items-center gap-2">
          <Button><Upload /> Upload evidence</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Reject finding</Button>
          <Button variant="link">Link</Button>
          <Button disabled>Disabled</Button>
          <Button disabled><span className="size-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" /> Saving…</Button>
          <Button size="icon" aria-label="Add"><Plus /></Button>
        </div>
      </Section>

      <Section title="Status badges" note="Icon + text + colour: never colour alone.">
        <BadgeRow label="Investigation">{investigationStatuses.map((s) => <StatusBadge key={s} kind="investigation" status={s} />)}</BadgeRow>
        <BadgeRow label="Evidence">{evidenceStatuses.map((s) => <StatusBadge key={s} kind="evidence" status={s} />)}</BadgeRow>
        <BadgeRow label="Review">{reviewStatuses.map((s) => <StatusBadge key={s} kind="review" status={s} />)}</BadgeRow>
        <BadgeRow label="Task">{taskStatuses.map((s) => <StatusBadge key={s} kind="task" status={s} />)}</BadgeRow>
        <BadgeRow label="Priority">{priorities.map((p) => <PriorityBadge key={p} priority={p} />)}</BadgeRow>
      </Section>

      <Section title="Provenance labels" note="Every derived fact says where it came from. Hover or focus for the meaning.">
        <BadgeRow label="Assertion">{assertionKinds.map((k) => <AssertionLabel key={k} kind={k} />)}</BadgeRow>
      </Section>

      <Section title="Confidence" note="Bars + word + score. Thresholds: ≥ 0.75 high, ≥ 0.50 medium.">
        <div className="flex flex-wrap gap-6">
          <ConfidenceIndicator score={0.89} />
          <ConfidenceIndicator score={0.62} />
          <ConfidenceIndicator score={0.31} />
        </div>
      </Section>

      <Section title="Identifiers">
        <div className="flex flex-wrap gap-2">
          {['CASE-2026-001', 'CCTV-001', 'GPS-001', 'CALL-001', 'P001', 'D001', 'V001', 'LOC-A', 'E104'].map((id) => (
            <IdTag key={id}>{id}</IdTag>
          ))}
        </div>
      </Section>

      <Section title="Workflow & processing">
        <div className="grid gap-6 lg:grid-cols-2">
          <WorkflowStepper stage="correlation" className="flex-wrap" />
          <ProcessingProgress percent={72} currentStep="Metadata extraction" nextStep="Entity identification" />
        </div>
      </Section>

      <Section title="Form controls">
        <div className="grid max-w-xl gap-3 sm:grid-cols-2">
          <Input placeholder="Search evidence…" aria-label="Search evidence" />
          <Select>
            <SelectTrigger className="w-full" aria-label="Evidence type">
              <SelectValue placeholder="Evidence type" />
            </SelectTrigger>
            <SelectContent>
              {['Video', 'Image', 'Document', 'GPS Data', 'Call Records'].map((type) => (
                <SelectItem key={type} value={type}>{type}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input placeholder="Disabled" disabled aria-label="Disabled input" />
          <Input placeholder="Invalid value" aria-invalid aria-label="Invalid input" />
        </div>
      </Section>

      <Section title="Tabs">
        <Tabs defaultValue="overview" className="max-w-xl">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
            <TabsTrigger value="audit">Audit trail</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="text-sm text-muted-foreground">Evidence summary goes here.</TabsContent>
          <TabsContent value="metadata" className="text-sm text-muted-foreground">EXIF, file and acquisition metadata.</TabsContent>
          <TabsContent value="audit" className="text-sm text-muted-foreground">Who viewed or changed this evidence.</TabsContent>
        </Tabs>
      </Section>

      <Section title="Overlays">
        <div className="flex flex-wrap gap-2">
          <Dialog>
            <DialogTrigger asChild><Button variant="outline">Open modal</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Reject potential relationship?</DialogTitle>
                <DialogDescription>The correlation stays in the audit log with your reason.</DialogDescription>
              </DialogHeader>
              <Input placeholder="Reason (required)" aria-label="Reason" />
              <DialogFooter>
                <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
                <DialogClose asChild><Button variant="destructive">Reject</Button></DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Sheet>
            <SheetTrigger asChild><Button variant="outline">Open drawer</Button></SheetTrigger>
            <SheetContent>
              <SheetHeader>
                <SheetTitle>CCTV-001</SheetTitle>
                <SheetDescription>Contextual details open in a drawer so the page behind stays in view.</SheetDescription>
              </SheetHeader>
            </SheetContent>
          </Sheet>
          <Tooltip>
            <TooltipTrigger asChild><Button variant="outline">Hover for tooltip</Button></TooltipTrigger>
            <TooltipContent>Tooltips explain; they never hold required information.</TooltipContent>
          </Tooltip>
          <Button variant="outline" onClick={() => toast.success('Evidence processing completed', { description: 'GPS-001 · 14 events extracted' })}>
            Success toast
          </Button>
          <Button variant="outline" onClick={() => toast.error('Evidence processing could not be completed', { description: 'Review the file format and try again.' })}>
            Error toast
          </Button>
        </div>
      </Section>

      <Section title="Loading, empty and error states">
        <div className="grid items-start gap-4 lg:grid-cols-3">
          <div className="space-y-2 rounded-lg border p-4">
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
          <EmptyState
            icon={FileStack}
            title="No evidence yet"
            description="No evidence has been added to this investigation yet."
            action={<Button size="sm"><Upload /> Add evidence</Button>}
          />
          <ErrorState
            description="Evidence processing could not be completed. Review the file format and try again."
            onRetry={() => toast.info('Retrying…')}
          />
        </div>
      </Section>
    </div>
  )
}

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="space-y-4">
      <div className="border-b pb-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {note && <p className="text-xs text-muted-foreground">{note}</p>}
      </div>
      {children}
    </section>
  )
}

function BadgeRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-24 text-xs text-muted-foreground">{label}</span>
      {children}
    </div>
  )
}
