'use client'

import { useEffect, useState } from 'react'
import { ArrowRight, Loader2 } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CameraTile } from '@/components/camera-tile'
import { ConnIndicator } from '@/components/conn-indicator'
import { Go2ChatBar } from '@/components/go2-chat-bar'
import { Mark } from '@/components/mark'
import { TextShimmer } from '@/components/ui/text-shimmer'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  COPY,
  LIVE_STEPS,
  ROBOTS,
  boot,
  bindSimplePlay,
  canCalibrate,
  chooseRobot,
  chooseSkill,
  copyFor,
  DEFAULT_SKILL,
  isBusy,
  onCalibrate,
  onPrimary,
  primaryAction,
  skillsForRobot,
  type PlaySnapshot,
  type RobotId,
  type SimpleStep,
  type SkillId,
  type StatusKind,
} from '@/lib/play'

const PRIMARY_LABEL = {
  start: 'Start engine',
  load: 'Load the unit',
  stop: 'Stop',
} as const

const PRIMARY_BUSY_LABEL = {
  start: 'Starting…',
  load: 'Loading…',
  stop: 'Stopping…',
} as const

const STEP_MARK: Record<SimpleStep, string> = {
  idle: 'OP_IDLE',
  connecting: 'OP_BOOT',
  choose: 'OP_UNIT',
  loading: 'OP_LOAD',
  calibrate: 'OP_CAL',
  apply: 'OP_APPLY',
  running: 'OP_RUN',
  error: 'OP_FAULT',
}

function Slash({ className }: { className?: string }) {
  return (
    <span className={className} aria-hidden="true">
      //
    </span>
  )
}

export function SimplePlay() {
  const [step, setStep] = useState<SimpleStep>('idle')
  const [robot, setRobot] = useState<RobotId | ''>('')
  const [skill, setSkill] = useState<SkillId>(DEFAULT_SKILL)
  const [status, setStatus] = useState('')
  const [kind, setKind] = useState<StatusKind>('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const sync = (next: PlaySnapshot) => {
      setStep(next.step)
      setRobot(next.robot)
      setSkill(next.skill)
      setStatus(next.status)
      setKind(next.kind)
      setBusy(isBusy())
    }
    bindSimplePlay({ paint: sync })
    boot()
  }, [])

  const engineScreen = step === 'idle' || step === 'connecting'
  const copy = engineScreen ? COPY.idle : copyFor(step, skill, robot)
  const offeredSkills = skillsForRobot(robot, skill)
  const mark = engineScreen ? STEP_MARK.idle : STEP_MARK[step]
  const action = primaryAction(step, robot)
  const showLive = LIVE_STEPS.has(step)
  const pickersLocked = busy || step === 'loading' || step === 'running'
  const headerAction =
    action === 'start' || action === 'load' || action === 'stop' ? action : null
  const ctaBusy =
    headerAction === 'start'
      ? busy || step === 'connecting'
      : headerAction === 'stop' && busy
  const primaryDisabled = ctaBusy || headerAction === 'load'
  const resetVisible = canCalibrate(step, robot)
  const resetBusy = busy && resetVisible && step !== 'running'

  return (
    <div className="flex h-dvh min-h-0 flex-col lg:flex-row">
      <main className="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden px-4 py-6 text-left">
      <header className="flex w-full shrink-0 flex-col items-start">
        <div className="mb-1 flex w-full items-center justify-between gap-3">
          <Mark className="min-w-0">{mark}</Mark>
          <ConnIndicator />
        </div>
        {engineScreen ? (
          <>
            <h1 className="text-base leading-5 font-semibold tracking-tight">
              {copy[0]}
            </h1>
            <p className="text-muted-foreground mt-1 text-[13px] leading-snug">
              {copy[1]}
            </p>
          </>
        ) : null}
      </header>

      <div className="mt-1.5 flex w-full shrink-0 flex-col items-start">
        {headerAction ? (
        <Button
          id="primary"
          size="sm"
          className="disabled:opacity-100"
          type="button"
          disabled={primaryDisabled}
          aria-busy={ctaBusy}
          onClick={() => {
            if (headerAction === 'load') return
            setBusy(true)
            void onPrimary()
          }}
        >
          {ctaBusy ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Slash className="text-brand-foreground/80 font-mono" />
          )}
          <span className="truncate whitespace-nowrap">
            {ctaBusy ? PRIMARY_BUSY_LABEL[headerAction] : PRIMARY_LABEL[headerAction]}
          </span>
          {headerAction === 'start' && !ctaBusy ? (
            <ArrowRight className="size-4" />
          ) : null}
        </Button>
        ) : null}
        <div
          id="status-slot"
          className="mt-1.5 min-h-[1.5rem] w-full text-left"
          aria-live="polite"
        >
          {kind === 'err' && status ? (
            <Alert id="status" variant="destructive" className="w-full">
              <AlertTitle className="font-mono tracking-wide">OP_FAULT</AlertTitle>
              <AlertDescription className="font-mono text-[13px] tabular-nums">
                {status}
              </AlertDescription>
            </Alert>
          ) : status && kind !== 'ok' ? (
            <p
              id="status"
              className="text-muted-foreground font-mono text-[13px] tabular-nums"
            >
              {kind === '' ? (
                <TextShimmer className="text-[13px] tracking-normal normal-case">
                  {status}
                </TextShimmer>
              ) : (
                status
              )}
            </p>
          ) : null}
        </div>
      </div>

      <div id="live-band" className="mt-4 flex min-h-0 w-full flex-1 flex-col">
        {showLive ? (
          <div className="mb-3 grid w-full shrink-0 grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-2 text-left">
              <Mark>UNIT</Mark>
              <Select
                value={robot || undefined}
                disabled={pickersLocked}
                onValueChange={(id) => {
                  void chooseRobot(id as RobotId)
                }}
              >
                <SelectTrigger id="unit-select" className="w-full">
                  <SelectValue placeholder="Load the unit" />
                </SelectTrigger>
                <SelectContent>
                  {ROBOTS.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2 text-left">
              <Mark>SKILL</Mark>
              <Select
                value={
                  offeredSkills.some((item) => item.id === skill)
                    ? skill
                    : undefined
                }
                disabled={pickersLocked}
                onValueChange={(id) => {
                  chooseSkill(id as SkillId)
                }}
              >
                <SelectTrigger id="skill-select" className="w-full">
                  <SelectValue placeholder="no skill yet — ask chat" />
                </SelectTrigger>
                <SelectContent>
                  {offeredSkills.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        ) : null}
        <div className="relative min-h-0 w-full flex-1">
          <CameraTile
            id="camera-top"
            mark="CAM_TOP"
            corner="01"
            alt="top"
            src="/api/camera/top/stream"
            className="absolute inset-0"
          />
          {showLive ? (
            <Badge
              variant="success"
              className="absolute bottom-3 left-1/2 z-20 -translate-x-1/2"
              id="live-pill"
            >
              <Slash className="text-success" />
              LIVE
            </Badge>
          ) : null}
        </div>
      </div>

      <footer
        id="simple-brand"
        className="flex w-full shrink-0 items-center justify-between gap-3 pt-4"
      >
        <div className="flex min-w-0 items-center gap-2">
        <img
          src="/static/openral-logo.svg"
          alt=""
          className="size-5 border border-border bg-card object-contain p-0.5"
        />
        <Mark className="normal-case tracking-[0.14em]">powered by openral</Mark>
        </div>
        {resetVisible ? (
          <Button
            id="reset"
            type="button"
            variant="ghost"
            size="sm"
            className="shrink-0"
            disabled={busy || !canCalibrate(step, robot)}
            aria-busy={resetBusy}
            aria-label="Reset"
            onClick={() => {
              setBusy(true)
              void onCalibrate()
            }}
          >
            {resetBusy ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Slash className="text-brand font-mono" />
            )}
            <span>{resetBusy ? 'RESETTING…' : 'RESET'}</span>
          </Button>
        ) : null}
      </footer>
      </main>
      <Go2ChatBar />
    </div>
  )
}
