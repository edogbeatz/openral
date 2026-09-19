/* OpenRAL simple dashboard — engine → UNIT → chat Apply.
   Load auto-stands (POST /api/demo/recalibrate) so Apply is ready.
   Footer RESET is the same Recalibrate (tip recovery; not the header CTA).
   Chat Apply stands first only if the dog is not already stood.
   SKILL stays empty until /simple chat proposes via Acquire.
   Never auto-walk. Abort is Stop (Hub stand), not End Cricket.
   Failures stay on the current step (fail in place) so Retry is the same CTA.
   Move uses demo_controls walk ids via POST /api/demo/walk.
   Hop is gym spring_jump ONNX (not mjlab hop crouch, not scripted squat).
   Hop uses POST /api/skill/execute. */

export const PLAY_KEY = 'openral.simple.play'
export const WRITE_CONTROLS_MSG =
  'write-controls disabled; set OPENRAL_DASHBOARD_WRITE_CONTROLS=1'
export const UNREACHABLE_MSG = "can't reach the dashboard"
export const CRICKET_DISCONNECTED_MSG = 'cricket is disconnected'
const RELOAD_POLL_MS = 2000
const RELOAD_MAX_TRIES = 90
const CRICKET_POLL_MS = 2000
const CRICKET_TOUCH_MIN_MS = 15000

export type RobotId = 'go2' | 'go2_z1'
export type SkillId =
  | ''
  | 'Acquire/rskill-rsl-rl-onnx-go2-velocity-flat'
  | 'OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32'
  | 'OpenRAL/rskill-zero-go2_z1-arm_ready-fp32'

export type WalkCommand =
  | ''
  | 'forward'
  | 'backward'
  | 'strafe_left'
  | 'strafe_right'
  | 'turn_left'
  | 'turn_right'
  | 'stop'

export interface SkillSpec {
  id: SkillId
  label: string
  embodimentTags: ReadonlyArray<string>
}
export type SimpleStep =
  | 'idle'
  | 'connecting'
  | 'choose'
  | 'loading'
  | 'calibrate'
  | 'apply'
  | 'running'
  | 'error'

export type StatusKind = '' | 'ok' | 'err'

export type PlaySnapshot = {
  step: SimpleStep
  robot: RobotId | ''
  skill: SkillId
  walkCommand: WalkCommand
  status: string
  kind: StatusKind
}

export const ROBOTS: ReadonlyArray<{
  id: RobotId
  label: string
  blurb: string
  image: string
}> = [
  {
    id: 'go2',
    label: 'Bare Go2',
    blurb: 'No arm',
    image: '/static/simple-ui/robots/go2.svg',
  },
  {
    id: 'go2_z1',
    label: 'Go2 + Z1',
    blurb: 'Arm robot',
    image: '/static/simple-ui/robots/go2-z1.svg',
  },
]

/** Default demo skills. Tags match in-tree rskill.yaml embodiment_tags. */
export const SKILLS: ReadonlyArray<SkillSpec> = [
  {
    id: 'Acquire/rskill-rsl-rl-onnx-go2-velocity-flat',
    label: 'move',
    embodimentTags: ['go2', 'go2_z1'],
  },
  {
    id: 'OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32',
    label: 'hop',
    embodimentTags: ['go2', 'go2_z1'],
  },
  {
    id: 'OpenRAL/rskill-zero-go2_z1-arm_ready-fp32',
    label: 'arm',
    embodimentTags: ['go2_z1'],
  },
]

export const DEFAULT_SKILL: SkillId = ''

export const WALK_VELOCITY_COMMANDS: Record<Exclude<WalkCommand, ''>, ReadonlyArray<number>> = {
  forward: [0.5, 0.0, 0.0],
  backward: [-0.3, 0.0, 0.0],
  strafe_left: [0.0, 0.25, 0.0],
  strafe_right: [0.0, -0.25, 0.0],
  turn_left: [0.0, 0.0, 0.6],
  turn_right: [0.0, 0.0, -0.6],
  stop: [0.0, 0.0, 0.0],
}
export const WALK_SKILL_IDS: ReadonlyArray<SkillId> = [
  'Acquire/rskill-rsl-rl-onnx-go2-velocity-flat',
]
export const HOP_SKILL_ID: SkillId = 'OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32'
export const ARM_SKILL_ID: SkillId = 'OpenRAL/rskill-zero-go2_z1-arm_ready-fp32'

export const COPY: Record<SimpleStep, [string, string]> = {
  idle: [
    'Start the engine',
    'Turn on cricket so the graph is live. Then load the unit.',
  ],
  connecting: ['Starting engine…', 'brev, tunnels, and the deploy-sim graph.'],
  choose: ['Load the unit', 'Nothing is loaded. Pick Bare Go2 or Go2 + Z1 (~30–90s).'],
  loading: ['Load the unit', 'Cold-reload. This page resumes when /healthz returns.'],
  calibrate: [
    'Calibrate',
    'No skill yet — ask chat. Footer RESET if tipped.',
  ],
  apply: [
    'Apply skill',
    'Stood. Ask chat for a skill, then Apply. Stop before it times out.',
  ],
  running: [
    'Running',
    'Stop stands the dog. Do not wait the 60s skill deadline.',
  ],
  error: ['Failed', 'The last action failed. Retry the same button.'],
}

export const LIVE_STEPS: ReadonlySet<SimpleStep> = new Set([
  'choose',
  'loading',
  'calibrate',
  'apply',
  'running',
])

const ALL_STEPS: ReadonlySet<SimpleStep> = new Set([
  'idle',
  'connecting',
  'choose',
  'loading',
  'calibrate',
  'apply',
  'running',
  'error',
])

type JsonMap = Record<string, unknown>

type SimpleUi = {
  paint: (next: PlaySnapshot) => void
}

let ui: SimpleUi | null = null
const playListeners = new Set<(next: PlaySnapshot) => void>()
let aborted = false
let busy = false
let cricketTouchAt = 0
let idleWatchGen = 0
let snapshot: PlaySnapshot = {
  step: 'idle',
  robot: '',
  skill: DEFAULT_SKILL,
  walkCommand: '',
  status: '',
  kind: '',
}

export function isBusy(): boolean {
  return busy
}

export function currentPlay(): PlaySnapshot {
  return snapshot
}

export function bindSimplePlay(next: SimpleUi): void {
  ui = next
}

export function subscribePlay(fn: (next: PlaySnapshot) => void): () => void {
  playListeners.add(fn)
  fn(snapshot)
  return () => {
    playListeners.delete(fn)
  }
}

function notifyPlay(): void {
  ui?.paint(snapshot)
  for (const fn of playListeners) fn(snapshot)
}

function persistPlay(): void {
  sessionStorage.setItem(
    PLAY_KEY,
    JSON.stringify({
      step: snapshot.step,
      robot: snapshot.robot,
      skill: snapshot.skill,
      walkCommand: snapshot.walkCommand,
    }),
  )
}

function paint(
  step: SimpleStep,
  extras?: Partial<Omit<PlaySnapshot, 'step'>>,
): void {
  snapshot = {
    step,
    robot: extras && extras.robot !== undefined ? extras.robot : snapshot.robot,
    skill: extras && extras.skill !== undefined ? extras.skill : snapshot.skill,
    walkCommand:
      extras && extras.walkCommand !== undefined
        ? extras.walkCommand
        : snapshot.walkCommand,
    status: extras && extras.status !== undefined ? extras.status : '',
    kind: extras && extras.kind !== undefined ? extras.kind : '',
  }
  persistPlay()
  notifyPlay()
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export function savePlay(
  step: SimpleStep,
  robot?: RobotId | '',
  skill?: SkillId,
  walkCommand?: WalkCommand,
): void {
  const rid = robot !== undefined ? robot : snapshot.robot
  const sid = skill !== undefined ? skill : snapshot.skill
  const cmd = walkCommand !== undefined ? walkCommand : snapshot.walkCommand
  sessionStorage.setItem(
    PLAY_KEY,
    JSON.stringify({ step, robot: rid, skill: sid, walkCommand: cmd }),
  )
}

function parseSkillId(value: unknown): SkillId {
  return SKILLS.some((item) => item.id === value) ? (value as SkillId) : ''
}

export function parseWalkCommand(value: unknown): WalkCommand {
  return value === 'forward' ||
    value === 'backward' ||
    value === 'strafe_left' ||
    value === 'strafe_right' ||
    value === 'turn_left' ||
    value === 'turn_right' ||
    value === 'stop'
    ? value
    : ''
}

export function parseRobotId(value: unknown): RobotId | '' {
  return value === 'go2' || value === 'go2_z1' ? value : ''
}

/** Visible /simple chat line when UNIT actually switches twins. */
export const UNIT_CHANGED_LINE = 'unit changed.'

/** Visible /simple chat line when the base tips past the 1 rad gate. */
export const FELL_LINE =
  'the unit fell. this skill needs retraining or finetuning.'

const FELL_POLL_MS = 1000

const unitChangedListeners = new Set<() => void>()
const fallenListeners = new Set<() => void>()
let fallenAnnounced = false

export function shouldAnnounceUnitChange(
  from: RobotId | '',
  to: RobotId | '',
): boolean {
  return Boolean(from && to && from !== to)
}

export function subscribeUnitChanged(fn: () => void): () => void {
  unitChangedListeners.add(fn)
  return () => {
    unitChangedListeners.delete(fn)
  }
}

export function noteUnitChanged(from: RobotId | '', to: RobotId | ''): void {
  if (!shouldAnnounceUnitChange(from, to)) return
  for (const fn of unitChangedListeners) fn()
}

export function fallenFromState(data: unknown): boolean {
  return Boolean(
    data && typeof data === 'object' && (data as { fallen?: unknown }).fallen === true,
  )
}

export function subscribeFallen(fn: () => void): () => void {
  fallenListeners.add(fn)
  return () => {
    fallenListeners.delete(fn)
  }
}

export function noteFallen(fallen: boolean): void {
  if (!fallen) {
    fallenAnnounced = false
    return
  }
  if (fallenAnnounced) return
  fallenAnnounced = true
  for (const fn of fallenListeners) fn()
}

async function pollFallen(): Promise<void> {
  try {
    const resp = await fetch('/api/state', { cache: 'no-store' })
    if (!resp.ok) return
    noteFallen(fallenFromState(await resp.json()))
  } catch {
    /* dashboard down */
  }
}

export function watchFallen(): () => void {
  void pollFallen()
  const id = window.setInterval(() => {
    void pollFallen()
  }, FELL_POLL_MS)
  return () => window.clearInterval(id)
}

export function robotLabel(id: RobotId | ''): string {
  if (id === 'go2_z1') return 'Go2 + Z1'
  if (id === 'go2') return 'Bare Go2'
  return ''
}

export function occupantRobot(opts: {
  stored: RobotId | ''
  live: RobotId | ''
  graphRunning: boolean
  loading: boolean
}): RobotId | '' {
  if (opts.loading && opts.stored) return opts.stored
  if (opts.graphRunning && opts.live) return opts.live
  return ''
}

export function loadPlay(): {
  step: SimpleStep
  robot: RobotId | ''
  skill: SkillId
  walkCommand: WalkCommand
} | null {
  try {
    const raw = sessionStorage.getItem(PLAY_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || !('step' in parsed)) return null
    const step = (parsed as { step: unknown }).step
    if (typeof step !== 'string' || !ALL_STEPS.has(step as SimpleStep)) return null
    return {
      step: step as SimpleStep,
      robot: parseRobotId((parsed as { robot?: unknown }).robot),
      skill: parseSkillId((parsed as { skill?: unknown }).skill),
      walkCommand: parseWalkCommand((parsed as { walkCommand?: unknown }).walkCommand),
    }
  } catch {
    return null
  }
}

export function isHopSkillId(skillId: string): boolean {
  const compact = skillId.trim().toLowerCase().replace(/-/g, '_')
  return compact.includes('hop') || compact.includes('jump')
}

export function isArmReadySkillId(skillId: string): boolean {
  const compact = skillId.trim().toLowerCase().replace(/-/g, '_')
  return compact.includes('arm_ready')
}

export function isWalkSkillId(skillId: string): boolean {
  const sid = skillId.trim()
  if (!sid) return false
  if (isHopSkillId(sid) || isArmReadySkillId(sid)) return false
  if (WALK_SKILL_IDS.includes(sid as SkillId)) return true
  if (sid === 'OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32') return true
  const compact = sid.toLowerCase().replace(/-/g, '_')
  return compact.includes('rsl_rl') && compact.includes('go2') && compact.includes('velocity')
}

export function skillsForRobot(
  robot: RobotId | '',
  offered: SkillId = '',
): ReadonlyArray<SkillSpec> {
  if (!robot || !offered) return []
  return SKILLS.filter((item) => item.id === offered)
}

export function clampSkillForRobot(skill: SkillId, robot: RobotId | ''): SkillId {
  if (!skill || !robot) return ''
  return SKILLS.some((item) => item.id === skill) ? skill : ''
}

export function skillLabel(skillId: string): string {
  const hit = SKILLS.find((item) => item.id === skillId)
  return hit ? hit.label : skillId
}

export function copyFor(
  step: SimpleStep,
  skill: SkillId,
  robot: RobotId | '' = '',
): [string, string] {
  const label = skillLabel(skill)
  const unit = robotLabel(robot)
  if ((step === 'choose' || step === 'loading') && !robot) {
    return [
      'Load the unit',
      'Nothing is loaded. Pick Bare Go2 or Go2 + Z1 (~30–90s).',
    ]
  }
  if (step === 'choose' && robot) {
    return [
      'Load the unit',
      unit + ' is the live twin. Switch UNIT to cold-reload the other (~30–90s).',
    ]
  }
  if (step === 'loading') {
    return [
      'Loading ' + unit,
      'Cold-reload ' + unit + '. This page resumes when that twin is live.',
    ]
  }
  if (step === 'apply') {
    if (!skill) {
      return [
        'Apply skill',
        'Stood. Ask chat for a skill, then Apply. Stop before it times out.',
      ]
    }
    return [
      'Apply skill',
      'Stood. Apply ' + label + ', then Stop before it times out.',
    ]
  }
  if (step === 'running') {
    return [
      'Running',
      'Stop stands the dog. Do not wait the 60s ' + label + ' deadline.',
    ]
  }
  return COPY[step]
}

export function reconcileRestoredPlay(opts: {
  stored: { step: SimpleStep; robot: RobotId | ''; skill: SkillId } | null
  liveRobot: RobotId | ''
  graphRunning: boolean
  skillRunning: boolean
}): { step: SimpleStep; robot: RobotId | '' } {
  const stored = opts.stored
  const robot = occupantRobot({
    stored: stored ? stored.robot : '',
    live: opts.liveRobot,
    graphRunning: opts.graphRunning,
    loading: Boolean(stored && stored.step === 'loading'),
  })
  if (opts.graphRunning && opts.skillRunning) {
    return { step: 'running', robot }
  }
  if (!opts.graphRunning) {
    if (stored && stored.step === 'connecting') {
      return { step: 'connecting', robot: '' }
    }
    if (stored && stored.step === 'loading' && stored.robot) {
      return { step: 'loading', robot: stored.robot }
    }
    return { step: 'idle', robot: '' }
  }
  if (stored && stored.step === 'apply') {
    return { step: 'apply', robot }
  }
  if (stored && stored.step === 'running') {
    return { step: 'apply', robot }
  }
  if (stored && stored.step === 'calibrate') {
    return { step: 'apply', robot }
  }
  if (stored && stored.step === 'loading') {
    return { step: 'calibrate', robot }
  }
  if (stored && stored.step === 'choose') {
    return { step: 'choose', robot }
  }
  if (stored && stored.step === 'connecting') {
    return { step: 'choose', robot }
  }
  return { step: 'choose', robot }
}

export function chooseSkill(id: SkillId): void {
  const skill = clampSkillForRobot(id, snapshot.robot)
  savePlay(snapshot.step, snapshot.robot, skill)
  paint(snapshot.step, {
    skill,
    status: snapshot.status,
    kind: snapshot.kind,
  })
}

export function applyAcquirePropose(raw: unknown): void {
  if (!raw || typeof raw !== 'object') {
    savePlay(snapshot.step, snapshot.robot, '', '')
    paint(snapshot.step, { skill: '', walkCommand: '' })
    return
  }
  const row = raw as {
    execute_id?: unknown
    walk_command?: unknown
    verdict?: unknown
  }
  const verdict = typeof row.verdict === 'string' ? row.verdict : ''
  if (verdict === 'adapt_offer') {
    savePlay(snapshot.step, snapshot.robot, '', '')
    paint(snapshot.step, { skill: '', walkCommand: '' })
    return
  }
  const skill = clampSkillForRobot(
    parseSkillId(typeof row.execute_id === 'string' ? row.execute_id : ''),
    snapshot.robot,
  )
  const walkCommand = parseWalkCommand(
    typeof row.walk_command === 'string' ? row.walk_command : '',
  )
  savePlay(snapshot.step, snapshot.robot, skill, walkCommand)
  paint(snapshot.step, {
    skill,
    walkCommand,
    status: snapshot.status,
    kind: snapshot.kind,
  })
}

export async function hydrateAcquirePropose(): Promise<void> {
  try {
    const resp = await fetch('/api/state', { cache: 'no-store' })
    if (!resp.ok) return
    const data = (await resp.json()) as { acquire_propose?: unknown }
    applyAcquirePropose(data.acquire_propose ?? null)
  } catch {
    /* dashboard down */
  }
}

export function primaryAction(
  step: SimpleStep,
  robot: RobotId | '' = '',
): 'start' | 'load' | 'stop' | 'none' {
  if (step === 'idle' || step === 'connecting') return 'start'
  if ((step === 'choose' || step === 'loading') && !robot) return 'load'
  if (step === 'running') return 'stop'
  return 'none'
}

export function canCalibrate(step: SimpleStep, robot: RobotId | ''): boolean {
  if (!robot) return false
  return (
    step === 'choose' ||
    step === 'calibrate' ||
    step === 'apply' ||
    step === 'error'
  )
}

export function canApply(step: SimpleStep, skill: SkillId = ''): boolean {
  if (!skill) return false
  return (
    step === 'choose' ||
    step === 'calibrate' ||
    step === 'apply' ||
    step === 'error'
  )
}

export type ChatApplyPhase = 'apply' | 'standing' | 'applying' | 'stop' | 'stopping'

export function chatApplyPhase(step: SimpleStep, busyFlag: boolean): ChatApplyPhase {
  if (step === 'running') return busyFlag ? 'stopping' : 'stop'
  if (!busyFlag) return 'apply'
  if (step === 'calibrate') return 'standing'
  return 'applying'
}

export function unreachableMessage(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err)
  if (
    err instanceof TypeError ||
    /failed to fetch|networkerror|load failed|aborted/i.test(msg)
  ) {
    return UNREACHABLE_MSG
  }
  return msg || UNREACHABLE_MSG
}

export function messageFromBody(
  data: JsonMap,
  resp: Response,
  fallback: string,
): string {
  if (resp.status === 403) {
    return String(data.error || WRITE_CONTROLS_MSG)
  }
  for (const key of ['error', 'detail', 'start_from_cold_hint'] as const) {
    const value = data[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return fallback + ' — HTTP ' + resp.status
}

export function classifyStartError(message: string): string {
  const text = message.trim()
  const lower = text.toLowerCase()
  if (
    lower.includes('write-controls') ||
    lower.includes('openral_dashboard_write_controls')
  ) {
    return WRITE_CONTROLS_MSG
  }
  if (/credit|insufficient|quota|billing/.test(lower)) {
    return text || 'Brev credits or billing blocked start'
  }
  if (
    /can't reach cricket|ssh never came up|ssh |unreachable cricket/.test(lower)
  ) {
    return text || "can't reach cricket (SSH)"
  }
  if (
    /not on path|source the workspace|ros2 cli not on path|cricket is disconnected|graph is not running|timed out calling|reset_to_pose failed|estop_reset timed out|did not accept the goal/.test(
      lower,
    )
  ) {
    return CRICKET_DISCONNECTED_MSG
  }
  if (/failed to fetch|networkerror|load failed/.test(lower)) {
    return UNREACHABLE_MSG
  }
  return text || UNREACHABLE_MSG
}

function startInFlight(): boolean {
  return busy || snapshot.step === 'connecting' || snapshot.step === 'loading'
}

function fail(step: SimpleStep, message: string, robot?: RobotId | ''): void {
  savePlay(step, robot)
  paint(step, {
    robot: robot !== undefined ? robot : snapshot.robot,
    status: message,
    kind: 'err',
  })
}

async function demoPost(
  url: string,
  body?: JsonMap,
): Promise<{ resp: Response; data: JsonMap }> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const opts: RequestInit = { method: 'POST', headers, cache: 'no-store' }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  try {
    const resp = await fetch(url, opts)
    let data: JsonMap = {}
    try {
      data = (await resp.json()) as JsonMap
    } catch {
      data = {}
    }
    return { resp, data }
  } catch (err) {
    throw new Error(unreachableMessage(err))
  }
}

export function touchIdle(): void {
  const now = Date.now()
  if (now - cricketTouchAt < CRICKET_TOUCH_MIN_MS) return
  cricketTouchAt = now
  void fetch('/api/demo/cricket/touch', { method: 'POST' }).catch(() => {})
}

async function ingestLive(): Promise<boolean> {
  try {
    const resp = await fetch('/api/state', { cache: 'no-store' })
    if (!resp.ok) return false
    const data = (await resp.json()) as JsonMap
    const last = data.last_ingest_ts
    const now = data.now_unix
    if (typeof last !== 'number' || last <= 0) return false
    const clock = typeof now === 'number' && now > 0 ? now : Date.now() / 1000
    return clock - last < 10
  } catch {
    return false
  }
}

async function cricketStatus(): Promise<JsonMap | null> {
  try {
    const resp = await fetch('/api/demo/cricket', { cache: 'no-store' })
    if (resp.status === 403) {
      throw new Error(WRITE_CONTROLS_MSG)
    }
    if (!resp.ok) return null
    return (await resp.json()) as JsonMap
  } catch (err) {
    if (err instanceof Error && err.message === WRITE_CONTROLS_MSG) throw err
    return null
  }
}

async function dashboardConfig(): Promise<JsonMap | null> {
  try {
    const resp = await fetch('/api/config', { cache: 'no-store' })
    if (!resp.ok) return null
    return (await resp.json()) as JsonMap
  } catch {
    return null
  }
}

async function waitForOccupant(wanted: RobotId): Promise<boolean> {
  let tries = 0
  let sawGap = false
  while (tries < RELOAD_MAX_TRIES) {
    if (aborted) return false
    tries += 1
    try {
      const cfg = await dashboardConfig()
      const live = parseRobotId(cfg && cfg.robot_id)
      if (live !== wanted) sawGap = true
      if (live === wanted && (sawGap || tries > 8)) return true
    } catch {
      sawGap = true
    }
    await sleep(RELOAD_POLL_MS)
  }
  return false
}

async function reloadAfterLoad(wanted: RobotId): Promise<boolean> {
  const up = await waitForOccupant(wanted)
  if (!up) throw new Error('reload timed out — refresh manually')
  if (aborted) return false
  await calibrate()
  return true
}

function startErrorFrom(data: JsonMap): string {
  for (const key of ['start_error', 'error'] as const) {
    const value = data[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

async function startCricket(): Promise<void> {
  const { resp, data } = await demoPost('/api/demo/cricket/start')
  if (resp.ok && data.already_running) {
    const cfg = await dashboardConfig()
    const live = parseRobotId(cfg && cfg.robot_id)
    savePlay('choose', live)
    paint('choose', {
      robot: live,
      status: String(data.detail || 'engine already up'),
      kind: 'ok',
    })
    return
  }
  const postedError = startErrorFrom(data)
  if (postedError) {
    throw new Error(classifyStartError(postedError))
  }
  if (resp.status === 202) {
    paint('connecting', {
      status: 'starting cricket graph… (~30-90s)',
      kind: '',
    })
    let tries = 0
    let misses = 0
    while (tries < 90) {
      if (aborted) return
      tries += 1
      const st = await cricketStatus()
      if (!st) {
        misses += 1
        if (misses >= 5) {
          throw new Error(UNREACHABLE_MSG)
        }
      } else {
        misses = 0
        if (st.graph_running) {
          const cfg = await dashboardConfig()
          const live = parseRobotId(cfg && cfg.robot_id)
          savePlay('choose', live)
          paint('choose', {
            robot: live,
            status: String(st.detail || 'engine up'),
            kind: 'ok',
          })
          return
        }
        const pollError = startErrorFrom(st)
        if (pollError) {
          throw new Error(classifyStartError(pollError))
        }
      }
      await sleep(CRICKET_POLL_MS)
    }
    throw new Error('start timed out — cricket graph never came up')
  }
  throw new Error(classifyStartError(messageFromBody(data, resp, 'start failed')))
}

async function finishLoad(robot: RobotId): Promise<void> {
  paint('loading', {
    robot,
    status: 'waiting for ' + robotLabel(robot) + '…',
    kind: '',
  })
  const up = await waitForOccupant(robot)
  if (!up) throw new Error('reload timed out')
  if (aborted) return
  await calibrate()
}

export async function onCalibrate(): Promise<void> {
  if (busy || snapshot.step === 'loading' || snapshot.step === 'running') return
  if (!snapshot.robot) {
    fail('choose', 'choose a robot first')
    return
  }
  busy = true
  aborted = false
  try {
    await calibrate()
  } catch (err) {
    fail('calibrate', classifyStartError(unreachableMessage(err)))
  } finally {
    busy = false
    notifyPlay()
  }
}

export async function onApply(): Promise<void> {
  if (busy) return
  if (!snapshot.robot) {
    fail('choose', 'choose a robot first')
    return
  }
  if (!clampSkillForRobot(snapshot.skill, snapshot.robot)) {
    await hydrateAcquirePropose()
  }
  if (!clampSkillForRobot(snapshot.skill, snapshot.robot)) {
    fail(snapshot.step === 'choose' ? 'choose' : snapshot.step, 'ask chat for a skill first')
    return
  }
  busy = true
  aborted = false
  const needsStand = snapshot.step !== 'apply'
  if (needsStand) {
    paint('calibrate', { status: 'standing…', kind: '' })
  } else {
    notifyPlay()
  }
  try {
    if (needsStand) {
      await calibrate()
    }
    if (aborted) return
    await applySkill()
  } catch (err) {
    fail(
      snapshot.step === 'running' ? 'running' : 'apply',
      classifyStartError(unreachableMessage(err)),
    )
  } finally {
    busy = false
    notifyPlay()
  }
}

export async function onStop(): Promise<void> {
  if (busy) return
  busy = true
  notifyPlay()
  try {
    await stopSkill()
  } finally {
    busy = false
    notifyPlay()
  }
}

export async function onPrimary(): Promise<void> {
  const action = primaryAction(snapshot.step, snapshot.robot)
  if (action === 'none' || action === 'load') return
  if (action === 'stop') {
    await onStop()
    return
  }
  if (action === 'start') {
    savePlay('connecting')
    paint('connecting', { status: 'starting cricket…', kind: '' })
    if (busy) return
    busy = true
    aborted = false
    try {
      await startCricket()
    } catch (err) {
      fail('idle', classifyStartError(unreachableMessage(err)))
    } finally {
      busy = false
      notifyPlay()
    }
    return
  }
}

export async function chooseRobot(preset: RobotId): Promise<void> {
  if (busy && snapshot.step !== 'choose') return
  if (snapshot.step === 'running') {
    await onStop()
    if (snapshot.kind === 'err') return
  }
  let cfg: JsonMap | null
  try {
    cfg = await dashboardConfig()
  } catch (err) {
    fail('choose', unreachableMessage(err), preset)
    return
  }
  if (!cfg) {
    fail('choose', UNREACHABLE_MSG, snapshot.robot)
    return
  }
  const liveId = parseRobotId(cfg.robot_id)
  const keep = clampSkillForRobot(snapshot.skill, preset)
  if (liveId === preset && snapshot.step !== 'loading') {
    if (snapshot.step === 'apply' || snapshot.step === 'running') {
      paint(snapshot.step, { robot: preset, skill: keep })
      return
    }
    savePlay('apply', preset, keep)
    paint('apply', {
      robot: preset,
      skill: keep,
      status: 'this robot is already loaded — Reset if tipped',
      kind: 'ok',
    })
    return
  }
  noteUnitChanged(liveId || snapshot.robot, preset)
  busy = true
  aborted = false
  try {
    savePlay('loading', preset, '', '')
    paint('loading', {
      robot: preset,
      skill: '',
      walkCommand: '',
      status: 'loading ' + robotLabel(preset) + '… (~30-90s)',
      kind: '',
    })
    const { resp, data } = await demoPost('/api/demo/load', { preset })
    if (resp.status !== 202) {
      throw new Error(messageFromBody(data, resp, 'load failed'))
    }
    await reloadAfterLoad(preset)
  } catch (err) {
    fail('choose', unreachableMessage(err), preset)
  } finally {
    busy = false
    notifyPlay()
  }
}

async function calibrate(): Promise<void> {
  savePlay('calibrate')
  paint('calibrate', { status: 'standing…', kind: '' })
  const { resp, data } = await demoPost('/api/demo/recalibrate')
  if (resp.ok && data.accepted) {
    savePlay('apply')
    paint('apply', {
      status: snapshot.skill
        ? 'stood — Apply ' + skillLabel(snapshot.skill) + ' in chat'
        : 'stood — ask chat, then Apply',
      kind: 'ok',
    })
    return
  }
  throw new Error(messageFromBody(data, resp, 'stand failed'))
}

async function applySkill(): Promise<void> {
  const skillId = clampSkillForRobot(snapshot.skill, snapshot.robot)
  if (!skillId) {
    throw new Error('ask chat for a skill first')
  }
  const label = skillLabel(skillId)
  paint('apply', { skill: skillId, status: 'applying ' + label + '…', kind: '' })
  const st = await cricketStatus()
  if (st && st.skill_running) {
    const stopped = await demoPost('/api/demo/stop')
    if (!(stopped.resp.ok && stopped.data.accepted)) {
      throw new Error(messageFromBody(stopped.data, stopped.resp, 'stop failed'))
    }
  }
  const walkBody: JsonMap = { skill_id: skillId }
  if (snapshot.walkCommand) {
    walkBody.velocity_commands = [...WALK_VELOCITY_COMMANDS[snapshot.walkCommand]]
  }
  const posted = isWalkSkillId(skillId)
    ? await demoPost('/api/demo/walk', walkBody)
    : await demoPost('/api/skill/execute', {
        skill_id: skillId,
        goal_params_json: '',
      })
  if (!(posted.resp.ok || posted.resp.status === 202)) {
    throw new Error(messageFromBody(posted.data, posted.resp, label + ' failed'))
  }
  savePlay('running')
  paint('running', {
    skill: skillId,
    status: label + ' running — Stop before the 60s deadline',
    kind: 'ok',
  })
  void watchSkill()
}

async function watchSkill(): Promise<void> {
  let misses = 0
  while (snapshot.step === 'running' && !aborted) {
    await sleep(1000)
    touchIdle()
    let st: JsonMap | null = null
    try {
      st = await cricketStatus()
    } catch {
      st = null
    }
    if (!st) {
      misses += 1
      if (misses === 5) {
        paint('running', {
          status: UNREACHABLE_MSG + ' — Stop still works',
          kind: 'err',
        })
      }
      continue
    }
    misses = 0
    if (st.skill_running === false) {
      savePlay('apply')
      paint('apply', {
        status: 'skill ended — Apply again in chat or Reset if tipped',
        kind: 'ok',
      })
      return
    }
  }
}

async function stopSkill(): Promise<void> {
  aborted = true
  paint('running', { status: 'stopping — Hub stand', kind: '' })
  try {
    const { resp, data } = await demoPost('/api/demo/stop')
    if (!(resp.ok && data.accepted)) {
      aborted = false
      fail('running', messageFromBody(data, resp, 'stop failed'))
      return
    }
  } catch (err) {
    aborted = false
    fail('running', unreachableMessage(err))
    return
  }
  aborted = false
  savePlay('apply')
  paint('apply', { status: 'skill canceled; holding Hub stand', kind: 'ok' })
}

export function boot(): void {
  document.addEventListener('pointerdown', touchIdle, { passive: true })
  document.addEventListener('keydown', touchIdle, { passive: true })
  watchFallen()
  const play = loadPlay()
  const skill = play ? play.skill : DEFAULT_SKILL
  if (play && play.step === 'connecting') {
    paint('connecting', { robot: '', skill, status: 'resuming…', kind: '' })
  } else if (play && play.step === 'loading' && play.robot) {
    paint('loading', {
      robot: play.robot,
      skill: clampSkillForRobot(skill, play.robot),
      status: 'loading ' + robotLabel(play.robot) + '… (~30-90s)',
      kind: '',
    })
  } else if (play && LIVE_STEPS.has(play.step)) {
    paint('choose', { robot: '', skill, status: '', kind: '' })
  } else {
    paint('idle', { robot: '', skill, status: '', kind: '' })
  }
  if (!play || play.step === 'idle') void watchIdleUntilGraph()
  void bootAsync()
}

async function probeGraphThenMaybeChoose(liveRobot: RobotId | ''): Promise<void> {
  if (startInFlight() || snapshot.step !== 'idle') return
  let robot = liveRobot
  if (!robot) {
    const cfg = await dashboardConfig()
    robot = parseRobotId(cfg && cfg.robot_id)
  }
  let up = await ingestLive()
  if (!up) {
    try {
      const st = await cricketStatus()
      up = Boolean(st && st.graph_running)
    } catch (err) {
      if (startInFlight()) return
      fail('idle', classifyStartError(unreachableMessage(err)), '')
      return
    }
  }
  if (startInFlight() || snapshot.step !== 'idle') return
  if (!up) return
  savePlay('choose', robot)
  paint('choose', {
    robot,
    status: robot
      ? robotLabel(robot) + ' is live — Reset if tipped or switch UNIT'
      : 'engine up — load the unit',
    kind: 'ok',
  })
}

async function watchIdleUntilGraph(): Promise<void> {
  const gen = (idleWatchGen += 1)
  while (gen === idleWatchGen && snapshot.step === 'idle' && !busy) {
    const cfg = await dashboardConfig()
    const robot = parseRobotId(cfg && cfg.robot_id)
    await probeGraphThenMaybeChoose(robot)
    if (snapshot.step !== 'idle' || gen !== idleWatchGen) return
    await sleep(CRICKET_POLL_MS)
  }
}

async function bootAsync(): Promise<void> {
  try {
    const play = loadPlay()
    const cfg = await dashboardConfig()
    if (!cfg) {
      if (startInFlight()) return
      fail(snapshot.step, UNREACHABLE_MSG, snapshot.robot)
      return
    }
    if (cfg.write_controls_enabled === false) {
      if (startInFlight()) return
      fail(snapshot.step, WRITE_CONTROLS_MSG, snapshot.robot)
      return
    }

    const liveRobot = parseRobotId(cfg.robot_id)

    let st: JsonMap | null = null
    try {
      st = await cricketStatus()
    } catch (err) {
      if (startInFlight()) return
      fail(snapshot.step, classifyStartError(unreachableMessage(err)), snapshot.robot)
      return
    }
    if (
      !st &&
      play &&
      (LIVE_STEPS.has(play.step) || play.step === 'connecting')
    ) {
      fail(play.step, UNREACHABLE_MSG, play.robot)
      return
    }

    const graphRunning = Boolean(st && st.graph_running)
    const skillRunning = Boolean(st && st.skill_running)

    if (play && play.step === 'connecting' && !graphRunning) {
      if (busy) return
      paint('connecting', {
        robot: '',
        skill: play.skill,
        status: 'resuming…',
        kind: '',
      })
      void onPrimary()
      return
    }

    if (busy && snapshot.step === 'loading') return

    if (play && play.step === 'loading' && play.robot) {
      if (busy) return
      busy = true
      try {
        await finishLoad(play.robot)
      } catch (err) {
        fail('choose', classifyStartError(unreachableMessage(err)), play.robot)
      } finally {
        busy = false
        notifyPlay()
      }
      return
    }

    const next = reconcileRestoredPlay({
      stored: play,
      liveRobot,
      graphRunning,
      skillRunning,
    })
    const skill = clampSkillForRobot(play ? play.skill : snapshot.skill, next.robot)
    savePlay(next.step, next.robot, skill)
    paint(next.step, {
      robot: next.robot,
      skill,
      status:
        next.step === 'running'
          ? 'skill running — Stop'
          : next.step === 'apply' && next.robot
            ? robotLabel(next.robot) + ' stood — ask chat, Reset if tipped'
          : next.step === 'choose' && graphRunning && next.robot
            ? robotLabel(next.robot) + ' is live — Reset if tipped or switch UNIT'
            : next.step === 'choose' && graphRunning
              ? 'engine up — load the unit'
              : next.step === 'loading' && next.robot
                ? 'loading ' + robotLabel(next.robot) + '… (~30-90s)'
                : '',
      kind: next.step === 'choose' && graphRunning ? 'ok' : '',
    })
    if (next.step === 'running') void watchSkill()
    if (next.step === 'idle') void watchIdleUntilGraph()
  } catch (err) {
    if (startInFlight()) return
    fail(snapshot.step, classifyStartError(unreachableMessage(err)), snapshot.robot)
  }
}
