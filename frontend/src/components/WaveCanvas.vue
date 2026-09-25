<template>
  <canvas ref="canvas" class="wave-canvas" />
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps({
  analyser: { type: Object, default: null },
  color: { type: String, default: '#3DFBD1' },
  bars: { type: Number, default: 56 },
})

const canvas = ref(null)
let raf = null

function draw() {
  const el = canvas.value
  const node = props.analyser
  if (!el || !node) return
  const dpr = window.devicePixelRatio || 1
  const rect = el.getBoundingClientRect()
  el.width = rect.width * dpr
  el.height = rect.height * dpr
  const ctx = el.getContext('2d')
  const data = new Uint8Array(node.frequencyBinCount)
  const step = Math.floor(data.length / props.bars)

  const loop = () => {
    raf = requestAnimationFrame(loop)
    node.getByteFrequencyData(data)
    const w = el.width, h = el.height
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = props.color
    const barW = (w / props.bars) * 0.55, gap = (w / props.bars) * 0.45
    for (let i = 0; i < props.bars; i++) {
      const v = data[i * step] / 255
      const bh = Math.max(h * 0.03, v * h * 0.82)
      ctx.globalAlpha = 0.32 + v * 0.68
      ctx.beginPath()
      ctx.roundRect(i * (barW + gap) + gap / 2, (h - bh) / 2, barW, bh, Math.min(4 * dpr, barW / 2))
      ctx.fill()
    }
    ctx.globalAlpha = 1
  }
  loop()
}

watch(() => props.analyser, (node) => {
  cancelAnimationFrame(raf)
  if (node) draw()
}, { immediate: true, flush: 'post' })

onUnmounted(() => cancelAnimationFrame(raf))
</script>

<style scoped>
.wave-canvas { width: 100%; height: 100%; display: block; }
</style>
