import { Compass } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/design-system/states'

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-3xl pt-10">
      <EmptyState
        icon={Compass}
        title="This page does not exist"
        description="The link may be outdated, or the address was typed incorrectly."
        action={
          <Button asChild>
            <Link to="/">Go to overview</Link>
          </Button>
        }
      />
    </div>
  )
}
