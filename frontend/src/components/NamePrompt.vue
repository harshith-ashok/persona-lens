<template>
  <div class="overlay open" role="dialog" aria-modal="true" aria-labelledby="name-title"
       @click.self="$emit('skip')" @keydown.esc="$emit('skip')">
    <div class="modal">
      <div class="m-kicker">Unmatched</div>
      <h2 id="name-title">Who was that?</h2>

      <div v-if="people.length" class="pick-mode">
        <button type="button" :class="{ active: !existing }" @click="existing = false">New person</button>
        <button type="button" :class="{ active: existing }" @click="existing = true">Someone I know</button>
      </div>

      <div v-if="faceUrl" class="face-row">
        <img :src="faceUrl" alt="Captured face" class="face-thumb" />
        <label class="face-check"><input type="checkbox" v-model="useFace" /> Use this photo to recognize them</label>
      </div>

      <template v-if="!existing">
        <div class="field" :class="{ invalid }">
          <label for="name-input">Name</label>
          <input id="name-input" ref="nameInput" type="text" autocomplete="off" v-model="name"
                 @input="invalid = false" @keyup.enter="submit" />
          <div class="err">Enter a name first.</div>
        </div>
        <div class="field">
          <label for="rel-input">Relationship</label>
          <select id="rel-input" v-model="relationship">
            <option value="">Select</option>
            <option v-for="r in RELATIONS" :key="r">{{ r }}</option>
          </select>
        </div>
      </template>
      <div v-else class="field" :class="{ invalid }">
        <label for="person-input">Person</label>
        <select id="person-input" v-model="personId" @change="invalid = false">
          <option value="">Select</option>
          <option v-for="p in people" :key="p.id" :value="p.id">{{ p.name }}{{ p.relation ? ' · ' + p.relation : '' }}</option>
        </select>
        <div class="err">Choose who this was.</div>
      </div>

      <p v-if="error" class="np-error">{{ error }}</p>

      <div class="modal-actions">
        <button class="btn ghost" type="button" :disabled="saving" @click="$emit('skip')">Skip</button>
        <button class="btn primary" type="button" :disabled="saving" @click="submit">
          {{ saving ? 'Saving…' : 'Save' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '@/lib/api'

const RELATIONS = ['Daughter', 'Son', 'Spouse', 'Grandchild', 'Sibling', 'Friend', 'Neighbor', 'Caregiver', 'Other']

const props = defineProps({
  sessionId: { type: String, required: true },
  faceBlob: { type: Object, default: null }, // frame captured during a vision session
  faceB64: { type: String, default: '' },    // frame already stored on the session (naming later)
  people: { type: Array, default: () => [] }, // known people, for "Someone I know"
})
const emit = defineEmits(['saved', 'skip'])

const name = ref('')
const relationship = ref('')
const useFace = ref(true)
const saving = ref(false)
const invalid = ref(false)
const error = ref('')
const nameInput = ref(null)
const existing = ref(false)
const personId = ref('')

const blobUrl = computed(() => (props.faceBlob ? URL.createObjectURL(props.faceBlob) : ''))
const faceUrl = computed(() => blobUrl.value || (props.faceB64 ? `data:image/jpeg;base64,${props.faceB64}` : ''))
onMounted(() => setTimeout(() => nameInput.value?.focus(), 60))
onUnmounted(() => blobUrl.value && URL.revokeObjectURL(blobUrl.value))

async function submit() {
  if (saving.value) return
  if (existing.value ? !personId.value : !name.value.trim()) {
    invalid.value = true
    nameInput.value?.focus()
    return
  }
  saving.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('session_id', props.sessionId)
    if (existing.value) {
      fd.append('person_id', personId.value)
    } else {
      fd.append('name', name.value.trim())
      if (relationship.value) fd.append('relationship', relationship.value)
    }
    if (useFace.value) {
      if (props.faceBlob) fd.append('face_image', props.faceBlob, 'face.jpg')
      else if (props.faceB64) fd.append('use_session_face', 'true')
    }
    emit('saved', (await api.post('/person/finalize', fd)).data)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.pick-mode { display: flex; gap: 4px; margin-bottom: 14px; padding: 3px; border: 1px solid var(--line); border-radius: 999px; }
.pick-mode button { flex: 1; background: none; border: none; color: var(--ink-dim); font-size: 12.5px; padding: 6px 0; border-radius: 999px; cursor: pointer; }
.pick-mode button.active { background: var(--glow); color: #04211B; }
.face-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.face-thumb { width: 56px; height: 56px; object-fit: cover; border-radius: 4px; border: 1px solid var(--id-dim); transform: scaleX(-1); }
.face-check { font-size: 12px; color: var(--ink-dim); display: flex; gap: 6px; align-items: center; }
.np-error { font-size: 12px; color: var(--rec); margin: 0; }
</style>
