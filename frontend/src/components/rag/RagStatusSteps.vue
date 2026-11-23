<script setup lang="ts">
import type { RagStep } from "@/composables/ragStream";

defineProps<{ steps: RagStep[]; live?: boolean }>();
</script>

<template>
  <ol v-if="steps.length" class="rag-steps" aria-live="polite">
    <li v-for="(s, i) in steps" :key="i" :class="{ on: live && i === steps.length - 1 }">
      {{ s.message }}
    </li>
  </ol>
</template>

<style scoped>
.rag-steps {
  list-style: none;
  margin: 10px 0 0;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(255, 252, 245, 0.72);
  border: 1px dashed rgba(139, 90, 43, 0.35);
}
.rag-steps li {
  font-size: 13px;
  line-height: 1.7;
  color: var(--dj-ink-soft, #4a3f32);
}
.rag-steps li.on {
  color: var(--dj-ink, #2a2218);
  font-weight: 600;
}
</style>
