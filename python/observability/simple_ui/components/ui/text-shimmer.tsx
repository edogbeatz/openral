import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * Waiting-state copy. CSS shine only (Magic UI AnimatedShinyText, MIT) —
 * no motion dep. Industrial HMI: mono, optional `//` mark, no blobs.
 */
export function TextShimmer({
  children,
  className,
  mark = false,
  id,
}: {
  children: ReactNode
  className?: string
  mark?: boolean
  id?: string
}) {
  return (
    <span
      id={id}
      className={cn(
        'text-shimmer inline-block font-mono text-[11px] font-medium tracking-[0.18em] uppercase',
        className,
      )}
    >
      {mark ? '// ' : null}
      {children}
    </span>
  )
}
