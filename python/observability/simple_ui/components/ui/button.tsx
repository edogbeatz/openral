import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import {
  controlHeightClass,
  controlHeightLgClass,
  controlHeightSmClass,
  controlHeightXlClass,
  controlIcon2xlClass,
  controlIconClass,
  controlIconLgClass,
  controlIconSmClass,
  controlIconXlClass,
  controlIconXsClass,
  controlRadiusClass,
  focusRingClass,
  pillRadiusClass,
} from '@/components/ui/control'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  `inline-flex items-center justify-center gap-2 whitespace-nowrap ${controlRadiusClass} text-sm font-medium uppercase tracking-[0.12em] transition-fast active:scale-[0.96] motion-reduce:transition-none motion-reduce:active:scale-100 disabled:pointer-events-none disabled:opacity-50 disabled:active:scale-100 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 ${focusRingClass} aria-invalid:ring-destructive aria-invalid:border-destructive`,
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        brand: 'bg-brand text-brand-foreground hover:bg-brand/90',
        destructive:
          'bg-destructive text-destructive-foreground hover:bg-destructive/90 focus-visible:ring-destructive',
        outline:
          'border bg-background shadow-xs hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50',
        secondary:
          'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        muted: 'bg-muted text-foreground hover:bg-muted/80',
        ghost:
          'hover:bg-accent hover:text-accent-foreground dark:hover:bg-accent/50',
        link: 'text-primary hover:text-primary/80 active:scale-100 tracking-normal normal-case',
        tile: 'bg-card text-foreground border border-border shadow-2xs hover:bg-accent',
      },
      size: {
        default: `${controlHeightClass} px-4 py-2 has-[>svg]:px-3`,
        sm: `${controlHeightSmClass} gap-1.5 px-3 has-[>svg]:px-2.5`,
        lg: `${controlHeightLgClass} px-6 has-[>svg]:px-4 [&_svg:not([class*='size-'])]:size-5`,
        xl: `${controlHeightXlClass} px-8 text-base has-[>svg]:px-6 [&_svg:not([class*='size-'])]:size-5`,
        icon: `${controlIconClass} ${pillRadiusClass}`,
        'icon-xs': `${controlIconXsClass} ${pillRadiusClass}`,
        'icon-sm': `${controlIconSmClass} ${pillRadiusClass}`,
        'icon-lg': `${controlIconLgClass} ${pillRadiusClass}`,
        'icon-xl': `${controlIconXlClass} ${pillRadiusClass}`,
        'icon-2xl': `${controlIcon2xlClass} ${pillRadiusClass}`,
      },
      shape: {
        default: '',
        pill: pillRadiusClass,
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
      shape: 'default',
    },
  },
)

function Button({
  className,
  variant,
  size,
  shape,
  asChild = false,
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : 'button'

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, shape, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
