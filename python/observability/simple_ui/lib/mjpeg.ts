/** MJPEG over fetch + canvas. `<img src=multipart>` remounts on spurious
 *  `error` and cannot drop late frames — that is the 3 fps slideshow. */

const JPEG_TYPE = 'image/jpeg'
const MAX_BUFFER = 2 * 1024 * 1024
const BOUNDARY = new TextEncoder().encode('--frame')
const HEADER_END = new TextEncoder().encode('\r\n\r\n')
const JPEG_SOI = new Uint8Array([0xff, 0xd8])
const JPEG_EOI = new Uint8Array([0xff, 0xd9])

export function indexOfBytes(
  haystack: Uint8Array,
  needle: Uint8Array,
  start = 0,
): number {
  const last = haystack.length - needle.length
  for (let i = start; i <= last; i += 1) {
    let matched = true
    for (let j = 0; j < needle.length; j += 1) {
      if (haystack[i + j] !== needle[j]) {
        matched = false
        break
      }
    }
    if (matched) return i
  }
  return -1
}

export function ownedBytes(bytes: Uint8Array): Uint8Array<ArrayBuffer> {
  const out = new Uint8Array(bytes.byteLength)
  out.set(bytes)
  return out
}

export function concatBytes(left: Uint8Array, right: Uint8Array): Uint8Array<ArrayBuffer> {
  if (left.length === 0) return ownedBytes(right)
  if (right.length === 0) return ownedBytes(left)
  const out = new Uint8Array(left.length + right.length)
  out.set(left, 0)
  out.set(right, left.length)
  return out
}

function contentLengthOf(header: string): number | null {
  const match = /content-length:\s*(\d+)/i.exec(header)
  if (!match) return null
  const size = Number(match[1])
  return Number.isFinite(size) && size >= 0 ? size : null
}

export function splitMjpegBuffer(buf: Uint8Array): {
  frames: Uint8Array[]
  rest: Uint8Array
} {
  const frames: Uint8Array[] = []
  const decoder = new TextDecoder()
  let offset = 0

  while (offset < buf.length) {
    const boundaryAt = indexOfBytes(buf, BOUNDARY, offset)
    if (boundaryAt < 0) {
      return { frames, rest: buf.subarray(offset) }
    }
    const headersEnd = indexOfBytes(buf, HEADER_END, boundaryAt)
    if (headersEnd < 0) {
      return { frames, rest: buf.subarray(boundaryAt) }
    }
    const header = decoder.decode(buf.subarray(boundaryAt, headersEnd))
    const bodyStart = headersEnd + HEADER_END.length
    const declared = contentLengthOf(header)
    if (declared !== null) {
      if (buf.length < bodyStart + declared) {
        return { frames, rest: buf.subarray(boundaryAt) }
      }
      frames.push(buf.subarray(bodyStart, bodyStart + declared))
      offset = bodyStart + declared
      continue
    }
    const soi = indexOfBytes(buf, JPEG_SOI, bodyStart)
    if (soi < 0) {
      return { frames, rest: buf.subarray(boundaryAt) }
    }
    const eoi = indexOfBytes(buf, JPEG_EOI, soi + 2)
    if (eoi < 0) {
      return { frames, rest: buf.subarray(boundaryAt) }
    }
    frames.push(buf.subarray(soi, eoi + JPEG_EOI.length))
    offset = eoi + JPEG_EOI.length
  }
  return { frames, rest: new Uint8Array(0) }
}

export function createLatestFramePainter(
  paint: (jpeg: Uint8Array) => Promise<void>,
): (jpeg: Uint8Array) => void {
  let pending: Uint8Array | null = null
  let busy = false

  async function pump(): Promise<void> {
    busy = true
    try {
      while (pending) {
        const next = pending
        pending = null
        await paint(next)
      }
    } finally {
      busy = false
      if (pending) void pump()
    }
  }

  return function submit(jpeg: Uint8Array): void {
    pending = jpeg
    if (!busy) void pump()
  }
}

export async function paintJpegToCanvas(
  canvas: HTMLCanvasElement,
  jpeg: Uint8Array,
): Promise<void> {
  const blob = new Blob([ownedBytes(jpeg)], { type: JPEG_TYPE })
  const bitmap = await createImageBitmap(blob)
  try {
    if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
      canvas.width = bitmap.width
      canvas.height = bitmap.height
    }
    const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true })
    if (!ctx) return
    ctx.drawImage(bitmap, 0, 0)
  } finally {
    bitmap.close()
  }
}

export async function consumeMjpegStream(
  src: string,
  signal: AbortSignal,
  onFrame: (jpeg: Uint8Array) => void,
): Promise<void> {
  const resp = await fetch(src, { signal, cache: 'no-store' })
  if (!resp.ok || !resp.body) {
    throw new Error(`mjpeg ${resp.status}`)
  }
  const reader = resp.body.getReader()
  let buf: Uint8Array<ArrayBuffer> = new Uint8Array(0)
  while (!signal.aborted) {
    const { done, value } = await reader.read()
    if (done) break
    if (!value || value.length === 0) continue
    buf = concatBytes(buf, value)
    const { frames, rest } = splitMjpegBuffer(buf)
    buf = rest.length > MAX_BUFFER ? new Uint8Array(0) : ownedBytes(rest)
    if (frames.length === 0) continue
    onFrame(ownedBytes(frames[frames.length - 1]))
  }
}
