import { cpSync, mkdirSync, rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const src = path.join(root, 'out')
const dest = path.resolve(
  root,
  '../src/openral_observability/dashboard/static/simple-ui',
)
rmSync(dest, { recursive: true, force: true })
mkdirSync(path.dirname(dest), { recursive: true })
cpSync(src, dest, { recursive: true })
