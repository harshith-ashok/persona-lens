<template>
  <div class="host-setup">
    <p class="who">Signed in as <b>{{ host?.username || '…' }}</b></p>
    <p class="lead">Your voice and your face are saved to this account, under this username. Every device you sign in on — web or the phone app — recognizes the same you.</p>

    <section class="step">
      <h3><span class="tick" :class="{ on: host?.voice_enrolled }">{{ host?.voice_enrolled ? '✓' : '1' }}</span> Your voice</h3>
      <p class="hint">Read five short sentences aloud. You will see what was understood as you speak, so we know your voice is picked up clearly.</p>
      <GuidedVoiceEnroll :enrolled="!!host?.voice_enrolled" @done="$emit('changed')" />
    </section>

    <section class="step">
      <h3><span class="tick" :class="{ on: host?.face_enrolled }">{{ host?.face_enrolled ? '✓' : '2' }}</span> Your face</h3>
      <p class="hint">So you are shown as "You" on camera, and never mistaken for a visitor.</p>
      <FaceEnroll :photo="host?.photo_b64 || ''" @saved="$emit('changed')" />
    </section>

    <div v-if="skippable" class="actions">
      <button class="btn ghost" type="button" @click="$emit('skip')">Skip for now</button>
      <button class="btn primary" type="button" @click="$emit('done')">Done</button>
    </div>
  </div>
</template>

<script setup>
import GuidedVoiceEnroll from './GuidedVoiceEnroll.vue'
import FaceEnroll from './FaceEnroll.vue'

defineProps({
  host: { type: Object, default: null }, // GET /host
  skippable: { type: Boolean, default: false },
})
defineEmits(['changed', 'skip', 'done'])
</script>

<style scoped>
.who { font-size: 15px; margin: 0 0 4px; }
.who b { color: var(--id); font-weight: 600; }
.lead { color: var(--ink-dim); font-size: 13px; line-height: 1.5; margin: 0 0 16px; }
.step { border-top: 1px solid var(--line); padding: 14px 0 6px; }
.step h3 { font-size: 15px; font-weight: 600; margin: 0 0 4px; display: flex; align-items: center; gap: 10px; }
.tick { width: 22px; height: 22px; border-radius: 50%; border: 1px solid var(--line-strong); display: grid; place-items: center; font-family: var(--font-mono); font-size: 11px; color: var(--ink-dim); }
.tick.on { background: var(--glow); border-color: var(--glow); color: #04211B; }
.hint { color: var(--ink-dim); font-size: 12px; margin: 0 0 8px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
</style>
