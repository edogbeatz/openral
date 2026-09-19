/* Header connection pill — same 4-state ingest-age contract as operator `/`.
   Age is dashboard-host `now_unix - last_ingest_ts`, not the browser clock
   and not "is EventSource up". */

export const CONN_LIVE_S = 10
export const CONN_DEAD_S = 60
export const CONN_POLL_MS = 5000
export const CONN_RETRY_MS = 1500

export type ConnKind = 'wait' | 'live' | 'stale' | 'dead'

export type ConnSnapshot = {
  kind: ConnKind
  label: string
}

export function classifyConn(opts: {
  lastIngestTs?: number | null
  nowUnix?: number | null
  unreachable?: boolean
}): ConnSnapshot {
  if (opts.unreachable) {
    return { kind: 'stale', label: 'reconnecting…' }
  }
  const lastIngestTs = opts.lastIngestTs
  if (!lastIngestTs) {
    return { kind: 'wait', label: 'waiting…' }
  }
  const nowUnix = opts.nowUnix
  const now =
    typeof nowUnix === 'number' && nowUnix > 0 ? nowUnix : Date.now() / 1000
  const dt = now - lastIngestTs
  if (dt < CONN_LIVE_S) {
    return { kind: 'live', label: 'live' }
  }
  if (dt < CONN_DEAD_S) {
    return { kind: 'stale', label: `stale (${dt.toFixed(0)}s)` }
  }
  return { kind: 'dead', label: `dead (${Math.floor(dt / 60)}m)` }
}

export function connFromState(data: unknown): ConnSnapshot {
  if (!data || typeof data !== 'object') {
    return classifyConn({ unreachable: true })
  }
  const row = data as Record<string, unknown>
  const lastIngestTs =
    typeof row.last_ingest_ts === 'number' ? row.last_ingest_ts : null
  const nowUnix = typeof row.now_unix === 'number' ? row.now_unix : null
  return classifyConn({ lastIngestTs, nowUnix })
}
