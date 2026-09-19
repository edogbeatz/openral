import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Mark } from '@/components/mark'

export function HmiFrame({
  children,
  mark,
  corner,
  className,
  ...props
}: React.ComponentProps<'div'> & {
  children: ReactNode
  mark?: string
  corner?: string
}) {
  return (
    <div className={cn('relative', className)} {...props}>
      <span className="hmi-tick hmi-tick-tl" />
      <span className="hmi-tick hmi-tick-tr" />
      <span className="hmi-tick hmi-tick-bl" />
      <span className="hmi-tick hmi-tick-br" />
      {mark ? (
        <Mark className="hmi-mark hmi-mark-tl bg-transparent text-white [&_[aria-hidden]]:text-white">
          {mark}
        </Mark>
      ) : null}
      {corner ? (
        <Mark className="hmi-mark hmi-mark-br bg-transparent text-white [&_[aria-hidden]]:text-white">
          {corner}
        </Mark>
      ) : null}
      {children}
    </div>
  )
}
