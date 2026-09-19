'use client'

import { useEffect, useState } from 'react'
import {
  CONN_POLL_MS,
  CONN_RETRY_MS,
  classifyConn,
  connFromState,
  type ConnSnapshot,
} from '@/lib/conn'
import { TextShimmer } from '@/components/ui/text-shimmer'
import { cn } from '@/lib/utils'

const INITIAL: ConnSnapshot = { kind: 'wait', label: 'waiting…' }

export function ConnIndicator() {
  const [conn, setConn] = useState<ConnSnapshot>(INITIAL)

  useEffect(() => {
    let cancelled = false
    let es: EventSource | null = null
    let retryTimer = 0
    let pollTimer = 0

    function apply(next: ConnSnapshot) {
      if (!cancelled) setConn(next)
    }

    function fromPayload(raw: string) {
      try {
        apply(connFromState(JSON.parse(raw) as unknown))
      } catch {
        // malformed: keep last paint
      }
    }

    async function pollState() {
      try {
        const resp = await fetch('/api/state', { cache: 'no-store' })
        if (!resp.ok) return
        apply(connFromState((await resp.json()) as unknown))
      } catch {
        // EventSource onerror owns reconnecting… — same as operator `/`.
      }
    }

    function connect() {
      if (cancelled) return
      if (es) es.close()
      es = new EventSource('/api/stream')
      es.onmessage = (event) => {
        fromPayload(event.data)
      }
      es.onerror = () => {
        apply(classifyConn({ unreachable: true }))
        es?.close()
        es = null
        if (cancelled) return
        retryTimer = window.setTimeout(connect, CONN_RETRY_MS)
      }
    }

    connect()
    void pollState()
    pollTimer = window.setInterval(() => {
      void pollState()
    }, CONN_POLL_MS)

    return () => {
      cancelled = true
      es?.close()
      window.clearTimeout(retryTimer)
      window.clearInterval(pollTimer)
    }
  }, [])

  return (
    <div
      id="conn"
      role="status"
      data-kind={conn.kind}
      className={cn(
        'conn inline-flex items-center gap-2.5 border bg-card/60 px-3 py-1.5 font-mono text-[11px] tracking-[0.14em] uppercase',
        conn.kind === 'wait' && 'border-border text-muted-foreground',
        conn.kind === 'live' && 'border-success/35 text-success',
        conn.kind === 'stale' && 'border-warning/35 text-warning',
        conn.kind === 'dead' && 'border-danger/35 text-danger',
      )}
    >
      <span className="conn-dot" aria-hidden="true" />
      <span id="conn-label">
        {conn.kind === 'wait' ? (
          <TextShimmer className="tracking-[0.14em]">{conn.label}</TextShimmer>
        ) : (
          conn.label
        )}
      </span>
    </div>
  )
}
