'use client'

import { useEffect, useState } from 'react'
import { defineRegistry } from '@json-render/react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Mark } from '@/components/mark'
import { go2ChatCatalog } from '@/lib/chat-catalog'
import {
  chatApplyPhase,
  currentPlay,
  isBusy,
  onApply,
  onStop,
  subscribePlay,
  type ChatApplyPhase,
  type PlaySnapshot,
} from '@/lib/play'
import { cn } from '@/lib/utils'

let sendYes: (() => void | Promise<void>) | null = null

export function bindChatSendYes(fn: (() => void | Promise<void>) | null): void {
  sendYes = fn
}

function Slash({ className }: { className?: string }) {
  return (
    <span className={className} aria-hidden="true">
      //
    </span>
  )
}

const APPLY_LABEL: Record<ChatApplyPhase, string> = {
  apply: '',
  standing: 'STANDING…',
  applying: 'APPLYING…',
  stop: 'STOP',
  stopping: 'STOPPING…',
}

function ChatCtaButton({
  props,
}: {
  props: { label: string; action: 'apply' | 'adapt' | 'stop' }
}) {
  const [play, setPlay] = useState<PlaySnapshot>(() => currentPlay())
  const [playBusy, setPlayBusy] = useState(() => isBusy())
  const [localBusy, setLocalBusy] = useState(false)

  useEffect(() => {
    return subscribePlay(() => {
      setPlay(currentPlay())
      setPlayBusy(isBusy())
    })
  }, [])

  const isAdapt = props.action === 'adapt'
  const applyPhase = chatApplyPhase(play.step, playBusy || localBusy)
  const inFlight =
    (!isAdapt &&
      (applyPhase === 'standing' ||
        applyPhase === 'applying' ||
        applyPhase === 'stopping')) ||
    (isAdapt && localBusy)
  const label = isAdapt
    ? localBusy
      ? 'ADAPTING…'
      : props.label
    : applyPhase === 'apply'
      ? props.label
      : APPLY_LABEL[applyPhase]
  const id = isAdapt ? 'chat-adapt' : 'chat-apply'

  return (
    <Button
      id={id}
      type="button"
      size="sm"
      className="mt-1 w-full disabled:opacity-100"
      disabled={inFlight}
      aria-busy={inFlight}
      onClick={() => {
        if (inFlight) return
        if (!isAdapt && applyPhase === 'stop') {
          setLocalBusy(true)
          void onStop().finally(() => setLocalBusy(false))
          return
        }
        if (isAdapt) {
          setLocalBusy(true)
          void Promise.resolve(sendYes?.()).finally(() => setLocalBusy(false))
          return
        }
        setLocalBusy(true)
        void onApply().finally(() => setLocalBusy(false))
      }}
    >
      {inFlight ? (
        <Loader2 className="size-4 animate-spin" />
      ) : (
        <Slash className="text-brand-foreground/80 font-mono" />
      )}
      <span>{label}</span>
    </Button>
  )
}

export const { registry: go2ChatRegistry, handlers: go2ChatHandlers } =
  defineRegistry(go2ChatCatalog, {
    components: {
      Stack: ({ children }) => (
        <div className="flex flex-col gap-2 text-left">{children}</div>
      ),
      StatusCard: ({ props, children }) => (
        <Card
          className={cn(
            'gap-2 py-3',
            props.kind === 'err' && 'border-destructive',
            props.kind === 'propose' && 'border-brand',
          )}
        >
          <CardHeader className="px-3">
            <Mark>{props.mark}</Mark>
            <CardTitle className="mt-1 text-sm tracking-[0.12em] uppercase">
              {props.title}
            </CardTitle>
            <CardDescription className="font-mono text-[12px] tabular-nums">
              {props.detail}
            </CardDescription>
          </CardHeader>
          {children ? (
            <CardContent className="flex flex-col gap-2 px-3">{children}</CardContent>
          ) : null}
        </Card>
      ),
      Kv: ({ props }) => (
        <div className="flex items-baseline justify-between gap-3 font-mono text-[11px] tracking-[0.08em] uppercase">
          <span className="text-muted-foreground shrink-0">{props.label}</span>
          <span className="min-w-0 truncate tabular-nums">{props.value}</span>
        </div>
      ),
      Button: ({ props }) => <ChatCtaButton props={props} />,
    },
    actions: {
      apply: async () => {
        await onApply()
      },
      adapt: async () => {
        await sendYes?.()
      },
      stop: async () => {
        await onStop()
      },
    },
  })
