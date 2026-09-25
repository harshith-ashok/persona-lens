import { reactive } from 'vue'

export const toasts = reactive([])
let nextId = 1

export function toast(message, ms = 2400) {
  const id = nextId++
  toasts.push({ id, message })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i !== -1) toasts.splice(i, 1)
  }, ms)
}
