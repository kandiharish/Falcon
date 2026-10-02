import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { FileUp, ShieldCheck, X } from 'lucide-react'
import { toast } from 'sonner'
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
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { EvidenceType } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useUploadEvidence } from '@/services/queries'
import { evidenceTypeTerms, guessEvidenceType } from '@/design-system/vocabulary'
import { formatBytes } from '@/lib/format'
import { cn } from '@/lib/utils'

interface Props {
  caseReference: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

const EMPTY = {
  evidenceType: '' as EvidenceType | '',
  source: '',
  description: '',
  collectedAt: '',
  locationText: '',
  latitude: '',
  longitude: '',
  tags: '',
}

/** Evidence upload (plan §11). The server fingerprints the file; the original is never changed. */
export function UploadEvidenceDialog({ caseReference, open, onOpenChange }: Props) {
  const upload = useUploadEvidence(caseReference)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState(0)
  const [fields, setFields] = useState(EMPTY)
  const [formError, setFormError] = useState<string | null>(null)

  const set = (key: keyof typeof EMPTY) => (value: string) => setFields((f) => ({ ...f, [key]: value }))

  const choose = (picked: File | undefined) => {
    if (!picked) return
    setFile(picked)
    setFormError(null)
    upload.reset()
    const guess = guessEvidenceType(picked.name)
    if (guess && !fields.evidenceType) setFields((f) => ({ ...f, evidenceType: guess }))
  }

  const reset = () => {
    setFile(null)
    setFields(EMPTY)
    setProgress(0)
    setFormError(null)
    upload.reset()
  }

  const close = (next: boolean) => {
    if (upload.isPending) return // don't abandon an upload half-way
    if (!next) reset()
    onOpenChange(next)
  }

  const submit = () => {
    if (!file) return setFormError('Choose a file to upload.')
    if (!fields.evidenceType) return setFormError('Choose the evidence type.')
    const hasLat = fields.latitude.trim() !== ''
    const hasLon = fields.longitude.trim() !== ''
    if (hasLat !== hasLon) return setFormError('Enter both latitude and longitude, or neither.')
    setFormError(null)
    upload.mutate(
      {
        input: {
          file,
          evidenceType: fields.evidenceType,
          source: fields.source,
          description: fields.description,
          // <input type="datetime-local"> has no zone: interpret it in the investigator's zone
          collectedAt: fields.collectedAt ? new Date(fields.collectedAt).toISOString() : null,
          locationText: fields.locationText,
          latitude: hasLat ? Number(fields.latitude) : null,
          longitude: hasLon ? Number(fields.longitude) : null,
          tags: fields.tags.split(',').map((t) => t.trim()).filter(Boolean),
        },
        onProgress: setProgress,
      },
      {
        onSuccess: (evidence) => {
          toast.success(`${evidence.reference} uploaded`, {
            description: `Fingerprint SHA-256 ${evidence.sha256.slice(0, 12)}… recorded. Processing has started.`,
          })
          reset()
          onOpenChange(false)
          navigate(`/investigations/${caseReference}/evidence/${evidence.reference}`)
        },
      },
    )
  }

  const error =
    formError ?? (upload.error instanceof ApiError ? upload.error.message : upload.error ? 'The upload failed.' : null)

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Add evidence to {caseReference}</DialogTitle>
          <DialogDescription>
            The original file is stored unchanged and fingerprinted (SHA-256). Processing runs in the background.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <p role="alert" className="rounded-md border border-destructive/25 bg-destructive/5 px-3 py-2 text-sm">
            {error}
          </p>
        )}

        {/* Drop zone: click, keyboard (Enter/Space) or drag & drop */}
        {file ? (
          <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3">
            <FileUp aria-hidden className="size-5 shrink-0 text-primary" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{file.name}</p>
              <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
            </div>
            {!upload.isPending && (
              <Button variant="ghost" size="icon-sm" aria-label="Remove file" onClick={() => setFile(null)}>
                <X />
              </Button>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              choose(e.dataTransfer.files[0])
            }}
            className={cn(
              'flex w-full flex-col items-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring',
              dragging ? 'border-primary bg-primary/5' : 'hover:bg-muted/50',
            )}
          >
            <FileUp aria-hidden className="size-6 text-muted-foreground" />
            <span className="text-sm font-medium">Drop a file here, or click to choose</span>
            <span className="text-xs text-muted-foreground">One file per evidence item</span>
          </button>
        )}
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            choose(e.target.files?.[0])
            e.target.value = ''
          }}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="ev-type">Evidence type</Label>
            <Select value={fields.evidenceType} onValueChange={set('evidenceType')}>
              <SelectTrigger id="ev-type" className="w-full">
                <SelectValue placeholder="Choose…" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(evidenceTypeTerms).map(([value, term]) => (
                  <SelectItem key={value} value={value}>
                    <term.icon /> {term.label}
                    <span className="text-xs text-muted-foreground">· {term.hint}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <TextField id="ev-source" label="Source" placeholder="e.g. Warehouse gate camera 3" value={fields.source} onChange={set('source')} />
          <div className="space-y-1.5">
            <Label htmlFor="ev-collected">
              Collected at <span className="font-normal text-muted-foreground">(optional)</span>
            </Label>
            <Input id="ev-collected" type="datetime-local" value={fields.collectedAt} onChange={(e) => set('collectedAt')(e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="ev-description">
              Description <span className="font-normal text-muted-foreground">(optional)</span>
            </Label>
            <Textarea id="ev-description" rows={2} value={fields.description} onChange={(e) => set('description')(e.target.value)} />
          </div>
          <TextField id="ev-location" label="Location" placeholder="e.g. Riverside Industrial Zone" value={fields.locationText} onChange={set('locationText')} />
          <div className="grid grid-cols-2 gap-2">
            <TextField id="ev-lat" label="Latitude" placeholder="17.3850" value={fields.latitude} onChange={set('latitude')} inputMode="decimal" />
            <TextField id="ev-lon" label="Longitude" placeholder="78.4867" value={fields.longitude} onChange={set('longitude')} inputMode="decimal" />
          </div>
          <div className="sm:col-span-2">
            <TextField id="ev-tags" label="Tags" placeholder="night, gate, vehicle" value={fields.tags} onChange={set('tags')} />
          </div>
        </div>

        {upload.isPending && (
          <div className="space-y-1.5" aria-live="polite">
            <div className="flex justify-between text-xs">
              <span>{progress < 100 ? 'Uploading…' : 'Fingerprinting and saving…'}</span>
              <span className="font-mono tabular-nums">{progress}%</span>
            </div>
            <Progress value={progress} aria-label="Upload progress" />
          </div>
        )}

        <p className="flex items-start gap-2 text-xs text-muted-foreground">
          <ShieldCheck aria-hidden className="mt-0.5 size-3.5 shrink-0 text-success" />
          Location and time found inside the file (e.g. photo GPS) are added automatically and labelled
          “Extracted”; values you type here are never overwritten.
        </p>

        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)} disabled={upload.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={upload.isPending}>
            {upload.isPending ? 'Uploading…' : 'Upload evidence'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TextField({
  id,
  label,
  value,
  onChange,
  placeholder,
  inputMode,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  inputMode?: 'decimal'
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>
        {label} <span className="font-normal text-muted-foreground">(optional)</span>
      </Label>
      <Input id={id} value={value} placeholder={placeholder} inputMode={inputMode} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}
