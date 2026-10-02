import { Controller, useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useInvestigationContext } from '@/app/investigation-context'
import { ApiError } from '@/services/apiClient'
import { useCreateInvestigation } from '@/services/queries'
import { CASE_TYPES, priorityTerms } from '@/design-system/vocabulary'
import { allTimeZones, browserTimeZone, zoneLabel } from '@/lib/time'

const schema = z.object({
  title: z.string().trim().min(3, 'Use at least 3 characters.').max(200),
  caseType: z.string().min(1, 'Choose a case type.'),
  priority: z.enum(['low', 'medium', 'high', 'critical']),
  location: z.string().trim().max(200),
  description: z.string().trim().max(5000),
  tags: z.string().max(400),
  timeZone: z.string().min(1, 'Choose the time zone of the place under investigation.'),
})
type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Create investigation (plan §10). New cases start as Draft with the creator as lead. */
export function NewInvestigationDialog({ open, onOpenChange }: Props) {
  const create = useCreateInvestigation()
  const navigate = useNavigate()
  const setCurrentInvestigation = useInvestigationContext((s) => s.setCurrentInvestigation)
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: '',
      caseType: '',
      priority: 'medium',
      location: '',
      description: '',
      tags: '',
      timeZone: browserTimeZone(),
    },
  })
  const { errors } = form.formState

  const onSubmit = form.handleSubmit((values) =>
    create.mutate(
      {
        ...values,
        tags: values.tags.split(',').map((t) => t.trim()).filter(Boolean),
      },
      {
        onSuccess: (investigation) => {
          toast.success(`${investigation.reference} created`, {
            description: 'The investigation starts as a draft. You are its lead investigator.',
          })
          form.reset()
          onOpenChange(false)
          setCurrentInvestigation(investigation.reference)
          navigate(`/investigations/${investigation.reference}`)
        },
      },
    ),
  )

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) create.reset()
        onOpenChange(next)
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New investigation</DialogTitle>
          <DialogDescription>
            A case number is assigned automatically. You can add evidence and team members next.
          </DialogDescription>
        </DialogHeader>

        <form id="new-investigation" onSubmit={onSubmit} noValidate className="space-y-4">
          {create.error && (
            <p role="alert" className="rounded-md border border-destructive/25 bg-destructive/5 px-3 py-2 text-sm">
              {create.error instanceof ApiError ? create.error.message : 'The investigation could not be created.'}
            </p>
          )}

          <Field label="Title" htmlFor="inv-title" error={errors.title?.message}>
            <Input id="inv-title" autoFocus aria-invalid={!!errors.title} {...form.register('title')} />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Case type" htmlFor="inv-type" error={errors.caseType?.message}>
              <Controller
                control={form.control}
                name="caseType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="inv-type" className="w-full" aria-invalid={!!errors.caseType}>
                      <SelectValue placeholder="Choose…" />
                    </SelectTrigger>
                    <SelectContent>
                      {CASE_TYPES.map((type) => (
                        <SelectItem key={type} value={type}>{type}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field label="Priority" htmlFor="inv-priority">
              <Controller
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="inv-priority" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(priorityTerms).map(([value, term]) => (
                        <SelectItem key={value} value={value}>{term.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
          </div>

          <Field
            label="Time zone"
            htmlFor="inv-zone"
            error={errors.timeZone?.message}
            hint="Where the events happened. Times in this case are shown — and typed times read — in this zone."
          >
            <Controller
              control={form.control}
              name="timeZone"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="inv-zone" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="max-h-72">
                    {allTimeZones().map((zone) => (
                      <SelectItem key={zone} value={zone}>{zoneLabel(zone)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </Field>

          <Field label="Location" htmlFor="inv-location" optional>
            <Input id="inv-location" placeholder="e.g. Riverside Industrial Zone" {...form.register('location')} />
          </Field>

          <Field label="Description" htmlFor="inv-description" optional>
            <Textarea id="inv-description" rows={3} {...form.register('description')} />
          </Field>

          <Field label="Tags" htmlFor="inv-tags" optional hint="Separate with commas, e.g. night, cctv">
            <Input id="inv-tags" {...form.register('tags')} />
          </Field>
        </form>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit" form="new-investigation" disabled={create.isPending}>
            {create.isPending ? 'Creating…' : 'Create investigation'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Field({
  label,
  htmlFor,
  error,
  hint,
  optional,
  children,
}: {
  label: string
  htmlFor: string
  error?: string
  hint?: string
  optional?: boolean
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>
        {label}
        {optional && <span className="font-normal text-muted-foreground"> (optional)</span>}
      </Label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  )
}
