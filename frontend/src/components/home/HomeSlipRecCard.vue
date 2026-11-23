<script setup lang="ts">
import { computed } from "vue";
import { slipImageSrc } from "@/composables/slipImage";

const props = defineProps<{
  slip: {
    id: number;
    code: string;
    title: string;
    site_name?: string | null;
    image_url?: string | null;
    snippet?: string;
    read_count?: number | null;
    catalog_fill?: boolean;
    corpus_hint?: string | null;
  };
  /** 是否展示「热度」角标（有 read_count 时） */
  showHeat?: boolean;
}>();

const showHeat = computed(() => props.showHeat !== false);

const imgSrc = computed(() => slipImageSrc(props.slip.image_url || null));

/** 标题仅为「简牍 + code」等模板时，不与释文摘录叠放两段 */
const isGenericTitle = computed(() => {
  const t = (props.slip.title || "").trim();
  const c = (props.slip.code || "").trim();
  return Boolean(c && (t === `简牍 ${c}` || t === `简牍${c}` || t === c));
});

/** 单列释文：有摘录且为模板题，避免标题与 snippet 重复 */
const snippetOnlyLayout = computed(
  () => Boolean((props.slip.snippet || "").trim()) && isGenericTitle.value
);

const heading = computed(() => {
  if (snippetOnlyLayout.value) return "";
  const t = (props.slip.title || "").trim();
  const c = (props.slip.code || "").trim();
  const sn = (props.slip.snippet || "").trim();
  if (!t) return sn ? sn.slice(0, 56) + (sn.length > 56 ? "…" : "") : "简牍";
  if (c && (t === `简牍 ${c}` || t === `简牍${c}` || t === c)) {
    return sn ? sn.slice(0, 56) + (sn.length > 56 ? "…" : "") : t;
  }
  return t.length > 72 ? `${t.slice(0, 72)}…` : t;
});

/** 自定义题且摘录与标题大量重复时只保留标题 */
const hideSnippetUnderTitle = computed(() => {
  if (snippetOnlyLayout.value) return false;
  const t = (props.slip.title || "").trim();
  const sn = (props.slip.snippet || "").trim();
  if (!t || !sn || sn.length < 12) return false;
  return sn.startsWith(t.slice(0, Math.min(24, t.length))) || t.startsWith(sn.slice(0, Math.min(24, sn.length)));
});
</script>

<template>
  <li class="rec-slip-card">
    <router-link class="rec-slip-link" :to="'/slip/' + slip.id">
      <div class="rec-slip-thumb" aria-hidden="true">
        <img v-if="imgSrc" :src="imgSrc" alt="" class="rec-slip-img" loading="lazy" />
        <div v-else class="rec-slip-ph">牍</div>
      </div>
      <div class="rec-slip-body">
        <div class="rec-slip-chips">
          <span v-if="showHeat && slip.read_count != null && slip.read_count > 0" class="chip chip--heat">
            热度 · {{ slip.read_count }}
          </span>
          <span v-if="slip.site_name" class="chip chip--site">{{ slip.site_name }}</span>
          <span v-else-if="slip.corpus_hint" class="chip chip--corpus">{{ slip.corpus_hint }}</span>
        </div>
        <template v-if="snippetOnlyLayout">
          <p class="rec-slip-kicker">释文摘录</p>
          <p class="rec-slip-snippet rec-slip-snippet--solo">{{ slip.snippet }}</p>
        </template>
        <template v-else>
          <h3 class="rec-slip-title">{{ heading }}</h3>
          <p v-if="slip.snippet && !hideSnippetUnderTitle" class="rec-slip-snippet">{{ slip.snippet }}</p>
        </template>
        <div class="rec-slip-foot">
          <span class="rec-slip-code">{{ slip.code }}</span>
          <span v-if="slip.catalog_fill" class="rec-slip-foot-note" title="来自牍库展卷补齐">展卷</span>
        </div>
      </div>
    </router-link>
  </li>
</template>

<style scoped>
.rec-slip-card {
  list-style: none;
  margin: 0;
}
.rec-slip-link {
  display: flex;
  gap: 12px;
  align-items: stretch;
  padding: 12px 14px;
  border-radius: var(--dj-radius-sm, 10px);
  border: 1px solid rgba(201, 176, 138, 0.42);
  background: linear-gradient(
    165deg,
    rgba(255, 251, 243, 0.98) 0%,
    rgba(252, 246, 234, 0.88) 50%,
    rgba(239, 226, 204, 0.28) 100%
  );
  text-decoration: none;
  color: inherit;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  min-height: 96px;
  box-shadow: 0 2px 10px rgba(42, 34, 24, 0.04);
}
.rec-slip-link:hover {
  border-color: rgba(166, 124, 82, 0.45);
  box-shadow: 0 6px 20px rgba(42, 34, 24, 0.08);
  transform: translateY(-1px);
}
.rec-slip-thumb {
  flex: 0 0 72px;
  width: 72px;
  border-radius: 6px;
  overflow: hidden;
  background: rgba(42, 34, 24, 0.06);
  border: 1px solid rgba(201, 176, 138, 0.35);
  align-self: center;
}
.rec-slip-img {
  width: 100%;
  height: 88px;
  object-fit: cover;
  object-position: center;
  display: block;
}
.rec-slip-ph {
  height: 88px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--dj-font-display, serif);
  font-size: 28px;
  color: rgba(124, 58, 33, 0.35);
}
.rec-slip-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rec-slip-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.chip {
  font-size: 10.5px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(166, 124, 82, 0.35);
  color: var(--dj-ink-soft);
  background: rgba(255, 251, 243, 0.9);
}
.chip--heat {
  border-color: rgba(154, 52, 18, 0.35);
  color: rgba(124, 58, 33, 0.95);
}
.chip--site {
  border-color: rgba(74, 143, 98, 0.35);
  color: rgba(45, 90, 62, 0.95);
}
.chip--corpus {
  border-color: rgba(47, 125, 109, 0.35);
  color: rgba(30, 88, 78, 0.92);
}
.rec-slip-kicker {
  margin: 0;
  font-size: 10.5px;
  letter-spacing: 0.12em;
  color: var(--dj-ink-soft);
  opacity: 0.88;
}
.rec-slip-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  letter-spacing: 0.03em;
  color: var(--dj-ink);
  font-family: var(--dj-font-body, "Noto Serif SC", SimSun, serif);
}
.rec-slip-snippet {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.58;
  color: var(--dj-ink-soft);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.rec-slip-snippet--solo {
  font-size: 12.5px;
  line-height: 1.62;
  color: var(--dj-ink);
  -webkit-line-clamp: 3;
  letter-spacing: 0.03em;
}
.rec-slip-foot {
  margin-top: auto;
  padding-top: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.rec-slip-code {
  font-size: 10.5px;
  letter-spacing: 0.05em;
  color: var(--dj-ink-soft);
  opacity: 0.85;
  font-family: ui-monospace, monospace;
}
.rec-slip-foot-note {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--dj-ink-soft);
  opacity: 0.65;
  letter-spacing: 0.08em;
}
html.dark .rec-slip-link {
  background: linear-gradient(
    165deg,
    rgba(42, 34, 24, 0.55) 0%,
    rgba(32, 28, 22, 0.42) 100%
  );
  border-color: rgba(201, 176, 138, 0.22);
}
html.dark .rec-slip-title {
  color: rgba(252, 246, 234, 0.94);
}
html.dark .rec-slip-snippet {
  color: rgba(239, 226, 204, 0.72);
}
html.dark .rec-slip-snippet--solo {
  color: rgba(252, 246, 234, 0.9);
}
html.dark .chip {
  background: rgba(22, 20, 18, 0.5);
  border-color: rgba(201, 176, 138, 0.25);
  color: rgba(239, 226, 204, 0.78);
}
</style>
