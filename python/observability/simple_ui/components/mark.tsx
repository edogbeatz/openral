import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Mark({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground',
        className,
      )}
    >
      <span className="text-brand mr-1.5" aria-hidden="true">
        //
      </span>
      {children}
    </span>
  )
}
