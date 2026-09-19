'use client'

import { useEffect, useRef, useState } from 'react'
import { HmiFrame } from '@/components/hmi-frame'
import {
  consumeMjpegStream,
  createLatestFramePainter,
  paintJpegToCanvas,
} from '@/lib/mjpeg'
import { cn } from '@/lib/utils'

const PROBE_MS = 3000
const RECONNECT_MS = 400
const RECONNECT_MAX_MS = 2000

interface CameraTileProps {
  id: string
  mark: string
  corner: string
  src: string
  alt: string
  className?: string
}

function latestJpgUrl(streamSrc: string): string {
  return streamSrc.replace(/\/stream(?:\?.*)?$/, '/latest.jpg')
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export function CameraTile({
  id,
  mark,
  corner,
  src,
  alt,
  className,
}: CameraTileProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [noSignal, setNoSignal] = useState(false)
  const [stillUrl, setStillUrl] = useState<string | null>(null)
  const [hasMjpeg, setHasMjpeg] = useState(false)
  const hasPixelsRef = useRef(false)

  useEffect(() => {
    hasPixelsRef.current = false
    setNoSignal(false)
    setHasMjpeg(false)
    setStillUrl(null)
  }, [src])

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null

    async function probeStill() {
      // Sibling still only until the canvas has a frame. Do not SSH-probe
      // occupancy, and do not keep hitting latest.jpg after video is live —
      // that shared the HTTP/1.1 pool with the stream and hitching the tile.
      if (hasPixelsRef.current) return
      try {
        const resp = await fetch(`${latestJpgUrl(src)}?t=${Date.now()}`, {
          cache: 'no-store',
        })
        if (cancelled || hasPixelsRef.current) return
        if (resp.status === 204) {
          setNoSignal(true)
          return
        }
        if (!resp.ok) return
        const blob = await resp.blob()
        if (cancelled || hasPixelsRef.current) return
        setNoSignal(false)
        const url = URL.createObjectURL(blob)
        if (objectUrl) URL.revokeObjectURL(objectUrl)
        objectUrl = url
        setStillUrl(url)
      } catch {
        if (!cancelled && !hasPixelsRef.current) setNoSignal(true)
      }
    }

    void probeStill()
    const timer = window.setInterval(() => {
      if (hasPixelsRef.current) {
        window.clearInterval(timer)
        return
      }
      void probeStill()
    }, PROBE_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [src])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ac = new AbortController()
    let cancelled = false
    const submit = createLatestFramePainter(async (jpeg) => {
      if (cancelled) return
      await paintJpegToCanvas(canvas, jpeg)
      if (cancelled) return
      hasPixelsRef.current = true
      setHasMjpeg(true)
      setNoSignal(false)
    })

    async function run(): Promise<void> {
      let delay = RECONNECT_MS
      while (!cancelled) {
        try {
          await consumeMjpegStream(src, ac.signal, submit)
          if (cancelled || ac.signal.aborted) return
          delay = RECONNECT_MS
        } catch {
          if (cancelled || ac.signal.aborted) return
        }
        await sleep(delay)
        delay = Math.min(delay * 2, RECONNECT_MAX_MS)
      }
    }
    void run()
    return () => {
      cancelled = true
      ac.abort()
    }
  }, [src])

  return (
    <HmiFrame
      id={id}
      mark={mark}
      corner={corner}
      className={cn(
        'camera h-full min-h-0 w-full border border-border',
        (hasMjpeg || stillUrl) && !noSignal && 'is-streaming',
        noSignal && 'has-no-signal',
        hasMjpeg && 'has-mjpeg',
        className,
      )}
    >
      {stillUrl ? (
        <img className="camera-still" alt="" src={stillUrl} />
      ) : null}
      <canvas ref={canvasRef} className="camera-stream" aria-label={alt} />
      <span className="camera-placeholder">{noSignal ? 'no signal' : 'connecting'}</span>
    </HmiFrame>
  )
}
