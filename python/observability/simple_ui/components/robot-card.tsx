'use client'

import { cn } from '@/lib/utils'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Mark } from '@/components/mark'
import { ROBOTS, type RobotId } from '@/lib/play'

const ROBOT_MARK: Record<RobotId, string> = {
  go2: 'GO2',
  go2_z1: 'GO2_Z1',
}

export function RobotCard({
  robotId,
  selected,
  disabled,
  onSelect,
}: {
  robotId: RobotId
  selected: boolean
  disabled: boolean
  onSelect: (id: RobotId) => void
}) {
  const robot = ROBOTS.find((item) => item.id === robotId)
  if (!robot) return null

  return (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={selected}
      data-robot={robot.id}
      className={cn(
        'text-left transition-transform active:scale-[0.96] motion-reduce:active:scale-100',
        'disabled:pointer-events-none disabled:opacity-50',
        'outline-none focus-visible:ring-2 focus-visible:ring-ring',
      )}
      onClick={() => onSelect(robot.id)}
    >
      <Card
        className={cn(
          'gap-0 overflow-hidden py-0 shadow-xs',
          selected && 'shadow-[inset_0_0_0_2px_var(--ring)]',
        )}
      >
        <div className="relative">
          <img
            src={robot.image}
            alt=""
            className="aspect-square w-full object-cover outline outline-1 outline-black/10 dark:outline-white/10"
          />
          <Mark className="absolute top-2 left-2 bg-background/85 px-1.5 py-0.5 text-foreground">
            {ROBOT_MARK[robot.id]}
          </Mark>
        </div>
        <CardHeader className="px-3 py-3">
          <CardTitle className="text-[15px]">{robot.label}</CardTitle>
          <CardDescription>{robot.blurb}</CardDescription>
        </CardHeader>
      </Card>
    </button>
  )
}
