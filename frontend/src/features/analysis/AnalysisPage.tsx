import { useState } from 'react'
import { Link } from 'react-router'
import { Bot, FolderSearch, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState } from '@/design-system/states'
import { useCurrentCase } from '@/features/extraction/useCaseAccess'
import { AssistantPanel } from './AssistantPanel'
import { AIStatusNote } from './components'
import { SearchPanel } from './SearchPanel'

/** Analysis workspace (plan §21–§23): the Investigation Assistant and natural-language search. */
export function AnalysisPage() {
  const caseRef = useCurrentCase()
  const [tab, setTab] = useState('assistant')

  if (!caseRef) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState icon={FolderSearch} title="No investigation selected" description="Choose an investigation in the top bar."
          action={<Button asChild variant="outline"><Link to="/investigations">Open investigations</Link></Button>} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageHeader
        eyebrow={<IdTag>{caseRef}</IdTag>}
        title="Analysis"
        description="Ask questions about this investigation in plain words. AI helps read the question and find the records; every answer points to its evidence and needs your review."
      />
      <AIStatusNote />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="assistant"><Bot /> Investigation Assistant</TabsTrigger>
          <TabsTrigger value="search"><Search /> Search in plain words</TabsTrigger>
        </TabsList>
        {/* forceMount keeps a running conversation alive when switching tabs */}
        <TabsContent value="assistant" forceMount className="pt-4 data-[state=inactive]:hidden">
          <AssistantPanel caseRef={caseRef} />
        </TabsContent>
        <TabsContent value="search" forceMount className="pt-4 data-[state=inactive]:hidden">
          <SearchPanel caseRef={caseRef} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
