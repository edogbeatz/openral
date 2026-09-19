import { defineCatalog } from '@json-render/core'
import { schema } from '@json-render/react/schema'
import { z } from 'zod'

export const go2ChatCatalog = defineCatalog(schema, {
  components: {
    Stack: {
      props: z.object({}),
      slots: ['default'],
      description: 'Vertical stack of chat status cards',
    },
    StatusCard: {
      props: z.object({
        mark: z.string(),
        title: z.string(),
        detail: z.string(),
        kind: z.enum(['ok', 'err', 'info', 'propose']),
      }),
      slots: ['default'],
      description: 'Go2 status card with a headline and key/value rows',
    },
    Kv: {
      props: z.object({
        label: z.string(),
        value: z.string(),
      }),
      description: 'One labelled reasoner or prompt field',
    },
    Button: {
      props: z.object({
        label: z.string(),
        action: z.enum(['apply', 'adapt', 'stop']),
      }),
      description: 'Chat CTA: Apply, Adapt onto Go2+Z1, or Stop a running skill',
    },
  },
  actions: {
    apply: { description: 'Apply the proposed rSkill (Stand first if needed)' },
    adapt: { description: 'Remap the walk onto Go2+Z1' },
    stop: { description: 'Cancel ExecuteRskill and Hub-stand (same as header Stop)' },
  },
})
