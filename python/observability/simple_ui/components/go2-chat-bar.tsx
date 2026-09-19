'use client'

import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import {
  JSONUIProvider,
  Renderer,
  useChatUI,
} from '@json-render/react'
import { ArrowUp, Loader2 } from 'lucide-react'
import { Streamdown } from 'streamdown'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Mark } from '@/components/mark'
import { TextShimmer } from '@/components/ui/text-shimmer'
import { go2ChatRegistry, go2ChatHandlers, bindChatSendYes } from '@/lib/chat-registry'
import {
  FELL_LINE,
  UNIT_CHANGED_LINE,
  hydrateAcquirePropose,
  subscribeFallen,
  subscribeUnitChanged,
} from '@/lib/play'
import { cn } from '@/lib/utils'

interface UnitNotice {
  at: number
  id: string
  text: string
}

function withUnitNotices<T>(
  messages: ReadonlyArray<T>,
  notices: ReadonlyArray<UnitNotice>,
): ReadonlyArray<
  | { kind: 'msg'; message: T; index: number }
  | { kind: 'notice'; id: string; text: string }
> {
  const out: Array<
    | { kind: 'msg'; message: T; index: number }
    | { kind: 'notice'; id: string; text: string }
  > = []
  let n = 0
  for (let i = 0; i < messages.length; i++) {
    while (n < notices.length && notices[n]!.at <= i) {
      out.push({ kind: 'notice', id: notices[n]!.id, text: notices[n]!.text })
      n += 1
    }
    out.push({ kind: 'msg', message: messages[i]!, index: i })
  }
  while (n < notices.length) {
    out.push({ kind: 'notice', id: notices[n]!.id, text: notices[n]!.text })
    n += 1
  }
  return out
}

function Slash({ className }: { className?: string }) {
  return (
    <span className={className} aria-hidden="true">
      //
    </span>
  )
}

function chatApi(): string {
  if (typeof window === 'undefined') return '/api/chat'
  return `${window.location.origin}/api/chat`
}

export function Go2ChatBar() {
  const { messages, isStreaming, error, send } = useChatUI({ api: chatApi() })
  const [draft, setDraft] = useState('')
  const [unitNotices, setUnitNotices] = useState<ReadonlyArray<UnitNotice>>([])
  const scrollerRef = useRef<HTMLDivElement>(null)
  const wasStreaming = useRef(false)
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  const busy = isStreaming
  const last = messages.at(-1)
  const thread = withUnitNotices(messages, unitNotices)
  const actionHandlers = useMemo(
    () => go2ChatHandlers(() => undefined, () => ({})),
    [],
  )
  const waitingOnPull =
    isStreaming &&
    (last === undefined ||
      last.role === 'user' ||
      (last.role === 'assistant' && last.text.trim() === ''))

  useEffect(() => {
    bindChatSendYes(() => send('yes'))
    return () => bindChatSendYes(null)
  }, [send])

  useEffect(() => {
    return subscribeUnitChanged(() => {
      const at = messagesRef.current.length
      setUnitNotices((prev) => [
        ...prev,
        {
          at,
          id: `unit-changed-${Date.now()}-${prev.length}`,
          text: UNIT_CHANGED_LINE,
        },
      ])
    })
  }, [])

  useEffect(() => {
    return subscribeFallen(() => {
      const at = messagesRef.current.length
      setUnitNotices((prev) => [
        ...prev,
        {
          at,
          id: `fell-${Date.now()}-${prev.length}`,
          text: FELL_LINE,
        },
      ])
    })
  }, [])

  useEffect(() => {
    const node = scrollerRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [messages, isStreaming, unitNotices])

  useEffect(() => {
    const finished = wasStreaming.current && !isStreaming
    wasStreaming.current = isStreaming
    if (!finished) return
    let cancelled = false
    void (async () => {
      try {
        if (cancelled) return
        await hydrateAcquirePropose()
      } catch {
        /* dashboard down */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [isStreaming])

  function submitDraft() {
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    void send(text)
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submitDraft()
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submitDraft()
    }
  }

  return (
    <JSONUIProvider registry={go2ChatRegistry} handlers={actionHandlers}>
    <aside
      id="go2-chat"
      className="bg-background flex w-full shrink-0 flex-col border-t lg:h-dvh lg:w-80 lg:border-t-0 lg:border-l"
    >
      <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <Mark>GO2 CHAT</Mark>
          <span className="text-muted-foreground shrink-0 font-mono text-[11px] tracking-[0.16em] uppercase">
            <Slash className="text-brand mr-1.5" />
            reasoner
          </span>
        </div>

        {messages.length > 0 || isStreaming || unitNotices.length > 0 ? (
          <div
            ref={scrollerRef}
            className="no-scrollbar flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto text-left"
            aria-live="polite"
            aria-busy={busy}
          >
            {thread.map((item) => {
              if (item.kind === 'notice') {
                return (
                  <div
                    key={item.id}
                    className="flex flex-col items-start gap-2"
                  >
                    <div className="bg-muted text-foreground max-w-[92%] px-3 py-2 text-sm leading-relaxed">
                      <Streamdown className="text-left [&_*]:text-inherit">
                        {item.text}
                      </Streamdown>
                    </div>
                  </div>
                )
              }
              const { message, index } = item
              const isLast = index === messages.length - 1
              const isAssistantStream =
                isStreaming && isLast && message.role === 'assistant'
              const showShimmer =
                isAssistantStream && message.text.trim() === ''
              const showStream = message.text.trim() !== ''
              return (
                <div
                  key={message.id}
                  className={cn(
                    'flex flex-col gap-2',
                    message.role === 'user' ? 'items-end' : 'items-start',
                  )}
                >
                  {showStream || showShimmer ? (
                    <div
                      className={cn(
                        'max-w-[92%] px-3 py-2 text-sm leading-relaxed',
                        message.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-foreground',
                      )}
                    >
                      {showShimmer ? (
                        <TextShimmer id="go2-chat-pulling" mark>
                          pulling
                        </TextShimmer>
                      ) : (
                        <Streamdown
                          className="text-left [&_*]:text-inherit"
                          isAnimating={isAssistantStream}
                          caret="block"
                        >
                          {message.text}
                        </Streamdown>
                      )}
                    </div>
                  ) : null}
                  {message.spec ? (
                    <div className="w-full max-w-[92%]">
                      <Renderer
                        spec={message.spec}
                        registry={go2ChatRegistry}
                        loading={isAssistantStream}
                      />
                    </div>
                  ) : null}
                </div>
              )
            })}
            {waitingOnPull && last?.role !== 'assistant' ? (
              <div className="flex flex-col items-start gap-2">
                <div className="bg-muted text-foreground max-w-[92%] px-3 py-2 text-sm leading-relaxed">
                  <TextShimmer id="go2-chat-pulling" mark>
                    pulling
                  </TextShimmer>
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-muted-foreground min-h-0 flex-1 text-left font-mono text-[12px] tracking-[0.08em]">
            Ask for a walk or hop. Acquire finds a fit or asks to adapt.
          </p>
        )}

        {error ? (
          <Alert variant="destructive">
            <AlertTitle className="font-mono tracking-wide">CHAT_FAULT</AlertTitle>
            <AlertDescription className="font-mono text-[13px] tabular-nums">
              {error.message}
            </AlertDescription>
          </Alert>
        ) : null}

        <form
          className="mt-auto flex w-full min-w-0 items-end gap-2"
          onSubmit={onSubmit}
        >
          <Textarea
            id="go2-chat-input"
            name="prompt"
            rows={1}
            cols={1}
            value={draft}
            disabled={busy}
            placeholder='e.g. "walk forward"'
            aria-label="Message Go2"
            className="field-sizing-fixed min-h-12 min-w-0 flex-1 resize-none"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
          />
          <Button
            id="go2-chat-send"
            type="submit"
            size="icon"
            disabled={busy || !draft.trim()}
            aria-label="Send"
            aria-busy={busy}
            className="shrink-0"
          >
            {busy ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ArrowUp className="size-4" />
            )}
          </Button>
        </form>
      </div>
    </aside>
    </JSONUIProvider>
  )
}
