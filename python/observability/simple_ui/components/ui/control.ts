/** Compact control — one step below default. */
export const controlHeightSmClass = 'h-10'

/** Shared height for inputs, default buttons, tabs, and other interactive controls. */
export const controlHeightClass = 'h-12'

/** Emphasized control — one step above default. */
export const controlHeightLgClass = 'h-14'

/** Hero / page CTA. */
export const controlHeightXlClass = 'h-16'

/** Select trigger — full `data-[size=*]` strings so Tailwind can see them. */
export const selectTriggerHeightClass =
  'data-[size=default]:h-12 data-[size=sm]:h-10'

/** Icon-only sizes — match the text-control height at the same step. */
export const controlIconXsClass = 'size-9'
export const controlIconSmClass = 'size-10'
export const controlIconClass = 'size-12'
export const controlIconLgClass = 'size-14'
export const controlIconXlClass = 'size-16'
export const controlIcon2xlClass = 'size-20'

/** Shared corner — square. Camera inner ticks are `.hmi-tick`, not a radius. */
export const controlRadiusClass = 'rounded-none'

/** Icon buttons stay square with the rest of the HMI. */
export const pillRadiusClass = 'rounded-none'

/** Card / panel — square. */
export const cardRadiusClass = 'rounded-none'

/** Nested surface inside a card. Square, same as the parent. */
export const cardNestedRadiusClass = 'rounded-none'

/** Overlay chrome (dialog / alert). Square, same as cards. */
export const overlayRadiusClass = 'rounded-none'

/** Unused — camera uses `.hmi-tick` inner brackets, not a clip-path bite. */
export const cutClass = 'cut'

/** Hover / press chrome. Maps to `--transition-fast` (150ms, ease-out-quart). */
export const transitionFastClass =
  'transition-fast motion-reduce:transition-none'

/**
 * Keyboard focus — one 2px stroke. Do not also set `border-ring` or
 * `ring-offset-*`; that stacked a second outline (the old shadcn halo).
 */
export const focusRingClass =
  'outline-none focus-visible:ring-2 focus-visible:ring-ring'

/** Same stroke, inset so overflow-hidden parents don't clip it. */
export const focusRingInsetClass =
  'outline-none ring-inset focus-visible:ring-2 focus-visible:ring-ring'

/** Composite fields (numeric amount) that focus the wrapper. */
export const focusWithinRingInsetClass =
  'ring-inset focus-within:ring-2 focus-within:ring-ring'

/**
 * Hover / press for muted wells. Matches `Button variant="muted"`.
 * Gate hover with `@media (hover: hover)` so touch does not stick.
 */
export const wellHoverClass =
  'cursor-pointer active:bg-muted/70 [@media(hover:hover)]:hover:bg-muted/80 [@media(hover:hover)]:hover:outline [@media(hover:hover)]:hover:outline-1 [@media(hover:hover)]:hover:-outline-offset-1 [@media(hover:hover)]:hover:outline-border focus-visible:outline-none'

/**
 * Tappable muted well — list rows and chooser cards.
 * Pair with layout classes (`flex`, `p-4`, `text-left`).
 */
export const wellInteractiveClass = [
  'bg-muted',
  cardRadiusClass,
  wellHoverClass,
  focusRingInsetClass,
  transitionFastClass,
].join(' ')

/** Icon badge on a muted well — recovery rows and chooser cards. */
export const iconWellClass =
  'bg-background border-border flex size-8 shrink-0 items-center justify-center rounded-none border'

/** @deprecated Use `controlHeightClass`. */
export const inputFieldHeightClass = controlHeightClass
