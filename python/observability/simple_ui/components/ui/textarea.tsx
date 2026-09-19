import * as React from 'react'

import { controlRadiusClass, focusRingClass } from '@/components/ui/control'
import { cn } from '@/lib/utils'

function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        `flex min-h-12 w-full ${controlRadiusClass} field-sizing-content border border-input bg-transparent px-3 py-2.5 text-sm shadow-xs transition-[color,box-shadow] ${focusRingClass} placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30`,
        className,
      )}
      {...props}
    />
  )
}

export { Textarea }
