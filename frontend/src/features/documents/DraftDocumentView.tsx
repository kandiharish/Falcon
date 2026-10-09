/**
 * A drafted legal document (certificate or letter) as paper: serif, black on white, with its
 * DRAFT notice on screen and a "check before signing" list. Printing hides the app around it.
 */
import { TriangleAlert } from 'lucide-react'
import type { DraftDocument } from '@/services/documentsService'
import { cn } from '@/lib/utils'

export function DraftDocumentView({ doc }: { doc: DraftDocument }) {
  return (
    <article className="mx-auto max-w-3xl space-y-6 rounded-lg border bg-white p-6 font-serif text-[0.95rem] leading-relaxed [font-variant-numeric:lining-nums_tabular-nums] text-neutral-900 shadow-sm sm:p-12 print:border-0 print:p-0 print:shadow-none">
      <p data-print="hide" className="flex gap-2 rounded-md border border-amber-600/40 bg-amber-50 p-3 font-sans text-xs text-amber-900">
        <TriangleAlert aria-hidden className="size-4 shrink-0" />
        {doc.notice}
      </p>
      <header className="space-y-1 text-center">
        <h1 className="text-base font-bold tracking-wide sm:text-lg">{doc.title}</h1>
        <p className="text-sm text-neutral-600">{doc.subtitle}</p>
        <p className="font-mono text-xs text-neutral-600">{doc.reference}</p>
      </header>

      {doc.sections.map((section, i) => (
        <section key={i} className="space-y-3 break-inside-avoid-page">
          {section.heading && <h2 className="border-b border-neutral-300 pb-1 font-sans text-sm font-semibold">{section.heading}</h2>}
          {section.paragraphs.map((p, j) => <p key={j} className="whitespace-pre-line">{p}</p>)}
          {section.fields.length > 0 && (
            <table className="w-full border-collapse text-sm">
              <tbody>
                {section.fields.map(([label, value]) => (
                  <tr key={label} className="align-top">
                    <th scope="row" className="w-2/5 border border-neutral-300 bg-neutral-50 px-2 py-1 text-left font-normal text-neutral-700">{label}</th>
                    <td className={cn('border border-neutral-300 px-2 py-1 break-words', /^[0-9a-f]{64}$/.test(value) && 'font-mono text-xs break-all')}>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {section.items.length > 0 && (
            <ol className="list-decimal space-y-1 pl-6">{section.items.map((item, j) => <li key={j}>{item}</li>)}</ol>
          )}
          {section.signatures.length > 0 && (
            <div className="flex flex-wrap gap-8 pt-10">
              {section.signatures.map((label) => (
                <p key={label} className="min-w-56 flex-1 border-t border-neutral-800 pt-1 text-sm whitespace-pre-line">{label}</p>
              ))}
            </div>
          )}
        </section>
      ))}

      {doc.to_check.length > 0 && (
        <section data-print="hide" className="space-y-2 rounded-md bg-neutral-100 p-4 font-sans text-sm">
          <h2 className="font-semibold">Before signing, check</h2>
          <ul className="list-disc space-y-1 pl-5">{doc.to_check.map((c) => <li key={c}>{c}</li>)}</ul>
        </section>
      )}
    </article>
  )
}
