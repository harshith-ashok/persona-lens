<template>
  <div class="toast-stack" aria-live="polite">
    <div v-for="t in toasts" :key="t.id" class="toast">{{ t.message }}</div>
  </div>
</template>

<script setup>
import { toasts } from '@/composables/useToast'
</script>
