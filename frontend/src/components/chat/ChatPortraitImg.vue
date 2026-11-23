<script setup lang="ts">
import { computed, ref, useAttrs, watch } from "vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  roleKey: string;
}>();

const attrs = useAttrs();

/** 先尝试正式 PNG，缺失则沿用现有 SVG 占位 */
const ext = ref<"png" | "svg">("png");

watch(
  () => props.roleKey,
  () => {
    ext.value = "png";
  }
);

const src = computed(() => `/chat-portraits/${props.roleKey}.${ext.value}`);

function onError() {
  if (ext.value === "png") ext.value = "svg";
}
</script>

<template>
  <img v-bind="attrs" :src="src" decoding="async" @error="onError" />
</template>
