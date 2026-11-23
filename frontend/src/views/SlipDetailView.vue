<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";
import { trackEvent } from "@/composables/track";
import { slipImageSrc } from "@/composables/slipImage";
import { pushRagStep, readRagEventStream, refLabel, refQuote, type RagStep } from "@/composables/ragStream";
import RagStatusSteps from "@/components/rag/RagStatusSteps.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const id = computed(() => Number(route.params.id));

const slip = ref<{
  id: number;
  code: string;
  title: string;
  transcription: string;
  vernacular: string;
  site_name: string | null;
  era: string | null;
  image_url: string | null;
  tags: string | null;
} | null>(null);
const guessQs = ref<string[]>([]);
const guessLoading = ref(false);

const ragQuestion = ref("");
const ragAnswer = ref("");
const ragRefs = ref<Array<Record<string, unknown>>>([]);
const ragLoading = ref(false);
const showRagRefs = ref(false);
const useStreamRag = ref(true);
const ragSteps = ref<RagStep[]>([]);
const refOpen = ref<Record<number, boolean>>({});
const slipSampleQs = [
  "此简中某词作何解？与同类文书体例如何对应？",
  "可否逐句指出释文与绎白的关键差异，并说明依据？",
  "此简涉及何种制度/事务（禀食、候长、簿籍等）？材料里有哪些线索？",
  "请把材料梳理成「人物—地名—事务—时间」四项要点。",
  "若要继续检索相似简牍，建议用哪些关键词或编号线索？",
];

const READER_STORE = "dj_reader_pref_v1";
/** 释文/绎白默认略小；可在「阅读」栏 A± 调节（11～17px） */
const readerFontPx = ref(13);
const readerLineHeight = ref(1.85);

const imgPreviewOpen = ref(false);
const imgScale = ref(1);
function openImgPreview() {
  imgScale.value = 1;
  imgPreviewOpen.value = true;
}
function zoomIn() {
  imgScale.value = Math.min(3, Math.round((imgScale.value + 0.15) * 100) / 100);
}
function zoomOut() {
  imgScale.value = Math.max(0.6, Math.round((imgScale.value - 0.15) * 100) / 100);
}
function zoomReset() {
  imgScale.value = 1;
}
function onImgWheel(e: WheelEvent) {
  // Ctrl+滚轮：缩放；普通滚轮留给容器滚动
  if (!e.ctrlKey) return;
  e.preventDefault();
  if (e.deltaY < 0) zoomIn();
  else zoomOut();
}

const transEl = ref<HTMLElement | null>(null);
const vernEl = ref<HTMLElement | null>(null);
const selectedText = ref("");
const selectedRegion = ref<"" | "trans" | "vern">("");

function _isNodeInside(node: Node | null, host: HTMLElement | null): boolean {
  if (!node || !host) return false;
  const el = node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;
  return !!el && host.contains(el);
}

function updateSelection() {
  const sel = window.getSelection?.();
  const t = (sel?.toString() || "").trim();
  if (!t || !sel || sel.rangeCount === 0) {
    selectedText.value = "";
    selectedRegion.value = "";
    return;
  }
  const r = sel.getRangeAt(0);
  const inTrans = _isNodeInside(r.startContainer, transEl.value);
  const inVern = _isNodeInside(r.startContainer, vernEl.value);
  const inside = inTrans || inVern;
  selectedText.value = inside ? t : "";
  selectedRegion.value = inside ? (inTrans ? "trans" : "vern") : "";
}

function loadReaderPref() {
  try {
    const raw = localStorage.getItem(READER_STORE);
    if (!raw) return;
    const obj = JSON.parse(raw) as { fontPx?: number; lineHeight?: number };
    if (typeof obj.fontPx === "number" && Number.isFinite(obj.fontPx))
      readerFontPx.value = Math.min(17, Math.max(11, Math.round(obj.fontPx)));
    if (typeof obj.lineHeight === "number" && obj.lineHeight >= 1.55 && obj.lineHeight <= 2.2)
      readerLineHeight.value = obj.lineHeight;
  } catch {
    /* ignore */
  }
}

function saveReaderPref() {
  localStorage.setItem(READER_STORE, JSON.stringify({ fontPx: readerFontPx.value, lineHeight: readerLineHeight.value }));
}

/** 无出土地、年代时不占版面 */
const slipMetaLine = computed(() => {
  const s = slip.value;
  if (!s) return "";
  const parts: string[] = [];
  const site = (s.site_name || "").trim();
  const era = (s.era || "").trim();
  if (site) parts.push(site);
  if (era) parts.push(era);
  return parts.join(" · ");
});

function formatRef(r: Record<string, unknown>): string {
  const code = r.code != null ? String(r.code) : "";
  const title = r.title != null ? String(r.title) : "简牍条目";
  const body =
    (r.snippet as string) ||
    [r.transcription, r.vernacular].filter(Boolean).join(" ") ||
    "";
  const short = body.length > 160 ? `${body.slice(0, 160)}…` : body;
  return code ? `「${code}」${title}${short ? ` — ${short}` : ""}` : `${title}${short ? ` — ${short}` : ""}`;
}

function toggleRef(i: number) {
  refOpen.value = { ...refOpen.value, [i]: !refOpen.value[i] };
}

async function load() {
  try {
    const { data } = await http.get(`/slips/${id.value}`);
    slip.value = data;
    trackEvent("slip_view", { slip_id: id.value });
  } catch {
    ElMessage.error("简牍不存在或加载失败");
    slip.value = null;
  }
}

async function loadGuess() {
  try {
    guessLoading.value = true;
    const { data } = await http.get(`/slips/${id.value}/suggested-questions`);
    guessQs.value = (data.questions as string[]) || [];
  } catch {
    guessQs.value = [];
  } finally {
    guessLoading.value = false;
  }
}

async function askRagOnSlip() {
  const q = ragQuestion.value.trim();
  if (!q) {
    ElMessage.warning("请先输入问题");
    return;
  }
  refOpen.value = {};
  if (useStreamRag.value) {
    await askRagOnSlipStream();
    return;
  }
  ragLoading.value = true;
  ragAnswer.value = "";
  ragRefs.value = [];
  showRagRefs.value = false;
  ragSteps.value = [{ stage: "retrieve", message: "正在检索简牍" }];
  try {
    const { data } = await http.post("/rag/query", {
      question: q,
      slip_id: id.value,
    });
    ragAnswer.value = data.answer as string;
    ragRefs.value = (data.references as Array<Record<string, unknown>>) || [];
    showRagRefs.value = ragRefs.value.length > 0;
    const steps = ((data.rag_meta?.steps || []) as RagStep[]);
    if (steps.length) ragSteps.value = steps;
    trackEvent("rag_query_slip_detail", { slip_id: id.value, q_len: q.length, refused: Boolean(data.refused) });
  } catch {
    ElMessage.error("牍师暂未能作答，请稍后再试");
  } finally {
    ragLoading.value = false;
  }
}

async function askRagOnSlipStream() {
  const q = ragQuestion.value.trim();
  if (!q) return;
  ragLoading.value = true;
  ragAnswer.value = "";
  ragRefs.value = [];
  ragSteps.value = [];
  showRagRefs.value = false;
  refOpen.value = {};
  try {
    const res = await fetch("/api/rag/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, slip_id: id.value }),
    });
    if (!res.ok) throw new Error("stream http");
    await readRagEventStream(res, {
      onStatus(step) {
        ragSteps.value = pushRagStep(ragSteps.value, step);
      },
      onToken(text) {
        ragAnswer.value += text;
      },
      onDone(done) {
        ragRefs.value = done.references || [];
        showRagRefs.value = ragRefs.value.length > 0;
      },
    });
    trackEvent("rag_query_slip_detail", { slip_id: id.value, q_len: q.length, stream: true });
  } catch {
    ElMessage.error("流式问牍失败，可改非流式重试");
  } finally {
    ragLoading.value = false;
  }
}

function onSlipAskKeydown(e: KeyboardEvent) {
  if (e.key !== "Enter") return;
  if ((e as any).isComposing) return;
  if (e.shiftKey) return;
  e.preventDefault();
  void askRagOnSlip();
}

function useSlipSample(q: string) {
  ragQuestion.value = q;
  document.getElementById("slip-rag")?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function fillAndAskFromGuess(q: string) {
  ragQuestion.value = q;
  void askRagOnSlip();
}

async function markRead() {
  if (!auth.token) {
    ElMessage.warning("请登录后记入掌阅");
    return;
  }
  try {
    await http.post("/user/progress/read", { slip_id: id.value });
    ElMessage.success("已记入掌阅");
  } catch {
    ElMessage.error("记录失败");
  }
}

function copyAll() {
  if (!slip.value) return;
  const t = `${slip.value.code}\n${slip.value.title}\n\n释文：${slip.value.transcription}\n\n绎白：${slip.value.vernacular}`;
  navigator.clipboard.writeText(t).then(
    () => ElMessage.success("全文已复制"),
    () => ElMessage.error("复制失败")
  );
}

function copySelection() {
  const t = selectedText.value.trim();
  if (!t) {
    ElMessage.info("请先在释文/绎白中选中一段文字");
    return;
  }
  navigator.clipboard.writeText(t).then(
    () => ElMessage.success("已复制选中文字"),
    () => ElMessage.error("复制失败")
  );
}

function copySelectionWithContext() {
  const t = selectedText.value.trim();
  const s = slip.value;
  if (!t || !s) {
    ElMessage.info("请先在释文/绎白中选中一段文字");
    return;
  }
  const sec = selectedRegion.value === "trans" ? "释文" : selectedRegion.value === "vern" ? "绎白" : "原文";
  const block = `${s.code} ${s.title}\n【${sec}节选】\n${t}`;
  navigator.clipboard.writeText(block).then(
    () => ElMessage.success("已复制（含题头）"),
    () => ElMessage.error("复制失败")
  );
}

function copyRagRefsList() {
  const s = slip.value;
  const refs = ragRefs.value || [];
  if (!refs.length) {
    ElMessage.info("暂无可复制的引用清单");
    return;
  }
  const head = s ? `${s.code} ${s.title}\n【所据简牍清单】` : "【所据简牍清单】";
  const lines = refs.map((r) => `- ${formatRef(r)}`);
  navigator.clipboard.writeText([head, ...lines].join("\n")).then(
    () => ElMessage.success("已复制引用清单"),
    () => ElMessage.error("复制失败")
  );
}

type CopyMode = "plain" | "md" | "md_quote";
const refsCopyMode = ref<CopyMode>("plain");

function _refLine(r: Record<string, unknown>, mode: CopyMode): string {
  const label = formatRef(r);
  const rid = typeof r.id === "number" ? r.id : null;
  if ((mode === "md" || mode === "md_quote") && rid != null) return `- [${label}](/slip/${rid})`;
  return `- ${label}`;
}

function _uniqueSortedRefs(refs: Array<Record<string, unknown>>): Array<Record<string, unknown>> {
  const seen = new Set<string>();
  const out: Array<Record<string, unknown>> = [];
  for (const r of refs || []) {
    const id = typeof r.id === "number" ? String(r.id) : "";
    const code = r.code != null ? String(r.code) : "";
    const title = r.title != null ? String(r.title) : "";
    const key = id ? `id:${id}` : `ct:${code}||${title}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(r);
  }
  const coll = new Intl.Collator("zh-Hans", { numeric: true, sensitivity: "base" });
  out.sort((a, b) => {
    const ac = a.code != null ? String(a.code) : "";
    const bc = b.code != null ? String(b.code) : "";
    const c1 = coll.compare(ac, bc);
    if (c1 !== 0) return c1;
    const at = a.title != null ? String(a.title) : "";
    const bt = b.title != null ? String(b.title) : "";
    return coll.compare(at, bt);
  });
  return out;
}

function copyRagRefsListByMode(mode: CopyMode) {
  const s = slip.value;
  const refs = _uniqueSortedRefs(ragRefs.value || []);
  if (!refs.length) {
    ElMessage.info("暂无可复制的引用清单");
    return;
  }
  refsCopyMode.value = mode;
  const head = s ? `${s.code} ${s.title}\n【所据简牍清单】` : "【所据简牍清单】";
  const lines = refs.map((r) => _refLine(r, mode));
  const text = [head, ...lines].join("\n");
  const out =
    mode === "md_quote"
      ? text
          .split("\n")
          .map((ln) => (ln.trim() ? `> ${ln}` : ">"))
          .join("\n")
      : text;
  navigator.clipboard.writeText(out).then(
    () => ElMessage.success(mode === "md" || mode === "md_quote" ? "已复制（Markdown 清单）" : "已复制（普通清单）"),
    () => ElMessage.error("复制失败")
  );
}

function copyRagQuoteBlock(mode: CopyMode) {
  const s = slip.value;
  const ans = (ragAnswer.value || "").trim();
  const refs = _uniqueSortedRefs(ragRefs.value || []);
  const q = (ragQuestion.value || "").trim();
  if (!ans) {
    ElMessage.info("暂无可复制的绎读内容");
    return;
  }
  refsCopyMode.value = mode;
  const title = s ? `${s.code} ${s.title}` : "问牍绎读";
  const lines: string[] = [];
  lines.push(`【引用块｜${title}】`);
  lines.push("——");
  if (q) {
    lines.push(`问题：${q}`);
    lines.push("");
  }
  lines.push(ans);
  if (refs.length) {
    lines.push("");
    lines.push("【所据简牍】");
    lines.push(...refs.map((r) => _refLine(r, mode)));
  }
  const text = lines.join("\n");
  const out =
    mode === "md_quote"
      ? text
          .split("\n")
          .map((ln) => (ln.trim() ? `> ${ln}` : ">"))
          .join("\n")
      : text;
  navigator.clipboard.writeText(out).then(
    () => ElMessage.success(mode === "md" || mode === "md_quote" ? "已复制引用块（Markdown）" : "已复制引用块"),
    () => ElMessage.error("复制失败")
  );
}

function copyRagAnswer() {
  const t = (ragAnswer.value || "").trim();
  if (!t) {
    ElMessage.info("暂无可复制的绎读内容");
    return;
  }
  navigator.clipboard.writeText(t).then(
    () => ElMessage.success("已复制绎读"),
    () => ElMessage.error("复制失败")
  );
}

function scrollToSection(sectionId: string) {
  document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function reloadAll() {
  await load();
  await loadGuess();
}

onMounted(() => {
  loadReaderPref();
  document.addEventListener("selectionchange", updateSelection);
  void reloadAll();
});

onUnmounted(() => {
  document.removeEventListener("selectionchange", updateSelection);
});

watch(id, () => {
  slip.value = null;
  guessQs.value = [];
  ragQuestion.value = "";
  ragAnswer.value = "";
  ragRefs.value = [];
  void reloadAll();
});
</script>

<template>
  <div class="page dj-page">
    <div class="back-row">
      <el-button text type="primary" aria-label="返回牍库" @click="router.push('/browse')">← 返回牍库</el-button>
      <div class="back-titles">
        <span class="dj-kicker back-kicker">展卷</span>
        <span class="dj-heading back-title">简牍详情</span>
      </div>
    </div>

    <el-skeleton v-if="!slip" :rows="10" animated />
    <el-card v-else class="dj-slip-card main-card">
      <template #header>
        <div class="head-row">
          <span class="code">{{ slip.code }}</span>
          <div class="actions">
            <el-button size="small" @click="copyAll">复制全文</el-button>
            <el-button size="small" :disabled="!selectedText" @click="copySelection">复制选中</el-button>
            <el-button size="small" :disabled="!selectedText" @click="copySelectionWithContext">复制选中·含题头</el-button>
            <el-button type="primary" plain size="small" @click="markRead">记入掌阅</el-button>
          </div>
        </div>
      </template>
      <h1 class="title dj-heading">{{ slip.title }}</h1>
      <p v-if="slipMetaLine" class="meta">{{ slipMetaLine }}</p>
      <div class="anchor-bar" role="navigation" aria-label="页面内容导航">
        <el-button size="small" text type="primary" @click="scrollToSection('sec-trans')">释文</el-button>
        <span class="a-dot" aria-hidden="true">·</span>
        <el-button size="small" text type="primary" @click="scrollToSection('sec-vern')">绎白</el-button>
        <span class="a-dot" aria-hidden="true">·</span>
        <el-button size="small" text type="primary" @click="scrollToSection('slip-rag')">本牍问牍</el-button>
        <span class="a-dot" aria-hidden="true">·</span>
        <el-button size="small" text type="primary" @click="scrollToSection('slip-guess')">猜你想问</el-button>
      </div>
      <div class="reader-bar">
        <span class="reader-lbl">阅读</span>
        <el-button-group class="reader-group">
          <el-button size="small" @click="() => { readerFontPx = Math.max(11, readerFontPx - 1); saveReaderPref(); }">A-</el-button>
          <el-button size="small" @click="() => { readerFontPx = Math.min(17, readerFontPx + 1); saveReaderPref(); }">A+</el-button>
        </el-button-group>
        <el-button-group class="reader-group">
          <el-button size="small" @click="() => { readerLineHeight = 1.65; saveReaderPref(); }">紧凑</el-button>
          <el-button size="small" @click="() => { readerLineHeight = 1.85; saveReaderPref(); }">适中</el-button>
          <el-button size="small" @click="() => { readerLineHeight = 2.05; saveReaderPref(); }">舒展</el-button>
        </el-button-group>
      </div>
      <p v-if="selectedText" class="sel-hint" role="status" aria-live="polite">
        已选中 {{ selectedText.length }} 字，可点「复制选中」或「复制选中·含题头」用于引用。
      </p>
      <div v-if="slipImageSrc(slip.image_url)" class="figure">
        <span class="rope rope-left" aria-hidden="true" />
        <span class="rope rope-right" aria-hidden="true" />
        <img
          :src="slipImageSrc(slip.image_url)"
          :alt="`简牍影像 ${slip.code}`"
          class="slip-img"
          loading="lazy"
          role="button"
          tabindex="0"
          aria-label="点击放大预览简牍影像"
          @click="openImgPreview"
          @keydown.enter.prevent="openImgPreview"
        />
        <p class="img-cap">简牍影像；点击可放大预览（Ctrl+滚轮缩放）。</p>
      </div>
      <el-divider content-position="left">释文</el-divider>
      <div id="sec-trans" class="sec-anchor" aria-hidden="true" />
      <pre
        ref="transEl"
        class="body"
        tabindex="0"
        :style="{ fontSize: readerFontPx + 'px', lineHeight: String(readerLineHeight) }"
      >{{ slip.transcription }}</pre>
      <el-divider content-position="left">绎白</el-divider>
      <div id="sec-vern" class="sec-anchor" aria-hidden="true" />
      <pre
        ref="vernEl"
        class="body"
        tabindex="0"
        :style="{ fontSize: readerFontPx + 'px', lineHeight: String(readerLineHeight) }"
      >{{ slip.vernacular }}</pre>
      <p v-if="slip.tags" class="tags">标签：{{ slip.tags }}</p>

      <div id="slip-rag" class="rag-on-slip">
        <h3 class="rag-title dj-heading">本牍问牍</h3>
        <p class="rag-hint">
          在本页向牍师提问：材料优先包含<strong>当前这枚简牍</strong>全文，并辅以牍库关键词检索；绎读仅供学习参考，仍以释文与白话为准。
        </p>
        <div class="rag-samples">
          <span class="rag-samples-label">示例问法：</span>
          <div class="rag-samples-chips">
            <el-tag
              v-for="(s, i) in slipSampleQs"
              :key="i"
              class="sample-chip"
              effect="plain"
              @click="useSlipSample(s)"
            >
              {{ s }}
            </el-tag>
          </div>
        </div>
        <el-input
          v-model="ragQuestion"
          type="textarea"
          :rows="3"
          placeholder="例如：此简中「簿」作何解？与候长文书有何关联？"
          aria-label="本牍问牍输入"
          @keydown="onSlipAskKeydown"
        />
        <p class="rag-tip">
          小贴士：问题里若包含<strong>编号</strong>、<strong>地名</strong>、<strong>制度词</strong>，检索更准；Shift+Enter 换行，Enter 直接呈问。
        </p>
        <div class="rag-actions">
          <el-switch v-model="useStreamRag" active-text="逐字呈献" inactive-text="全篇呈览" class="stream-sw" />
          <el-button type="primary" :loading="ragLoading" @click="askRagOnSlip">呈问</el-button>
        </div>
        <RagStatusSteps :steps="ragSteps" :live="ragLoading" />
        <div v-if="ragLoading || ragAnswer" class="rag-answer dj-answer-surface">
          <div class="answer-head">
            <h4 class="answer-label dj-heading">绎读</h4>
            <div class="ans-actions">
              <el-button size="small" :disabled="!ragAnswer" @click="copyRagAnswer">复制绎读</el-button>
              <el-dropdown trigger="click">
                <el-button size="small" :disabled="!ragAnswer" plain>复制引用块</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="copyRagQuoteBlock('plain')">普通文本</el-dropdown-item>
                    <el-dropdown-item @click="copyRagQuoteBlock('md')">论坛 Markdown（带链接）</el-dropdown-item>
                    <el-dropdown-item @click="copyRagQuoteBlock('md_quote')">论坛引用（>）+ 链接</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <el-skeleton v-if="ragLoading && !ragAnswer" :rows="4" animated />
          <p v-else class="answer-body">
            {{ ragAnswer }}<span v-if="ragLoading && useStreamRag" class="stream-caret" aria-hidden="true" />
          </p>
          <template v-if="ragRefs.length">
            <div class="refs-head">
              <h4 class="answer-label dj-heading refs-title">所据简牍</h4>
              <div class="refs-actions">
                <el-button text type="primary" class="refs-toggle" @click="showRagRefs = !showRagRefs">
                  {{ showRagRefs ? "收起" : `展开（${ragRefs.length}）` }}
                </el-button>
                <el-dropdown trigger="click">
                  <el-button text type="primary" class="refs-copy">复制清单</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="copyRagRefsListByMode('plain')">普通列表</el-dropdown-item>
                      <el-dropdown-item @click="copyRagRefsListByMode('md')">论坛 Markdown（带链接）</el-dropdown-item>
                      <el-dropdown-item @click="copyRagRefsListByMode('md_quote')">论坛引用（>）+ 链接</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
            <el-collapse-transition>
              <ul v-show="showRagRefs" class="ref-list">
                <li v-for="(r, i) in ragRefs" :key="i">
                  <div class="ref-line">
                    <router-link
                      v-if="typeof r.id === 'number'"
                      class="ref-link"
                      :to="'/slip/' + r.id"
                    >
                      [{{ i + 1 }}] {{ refLabel(r) }}
                    </router-link>
                    <span v-else>[{{ i + 1 }}] {{ refLabel(r) }}</span>
                    <span v-if="r.via" class="ref-via">{{ r.via }}</span>
                    <button type="button" class="ref-expand" @click="toggleRef(i)">
                      {{ refOpen[i] ? "收起释文" : "展开释文" }}
                    </button>
                  </div>
                  <pre v-if="refOpen[i]" class="ref-quote">{{ refQuote(r) }}</pre>
                </li>
              </ul>
            </el-collapse-transition>
          </template>
        </div>
      </div>

      <div v-if="guessQs.length" id="slip-guess" class="guess-box">
        <div class="guess-head">
          <h3 class="guess-title dj-heading">猜你想问</h3>
          <el-button size="small" :loading="guessLoading" @click="loadGuess">换一批</el-button>
        </div>
        <p class="guess-hint">
          点选一问，即于<strong>本页</strong>呈问牍师并显示绎读；三条提示由当前释文与白话生成，可再自行改问。
        </p>
        <div class="guess-chips">
          <el-button
            v-for="(q, i) in guessQs"
            :key="i"
            size="small"
            type="primary"
            plain
            class="guess-btn"
            :disabled="ragLoading"
            @click="fillAndAskFromGuess(q)"
          >
            {{ q }}
          </el-button>
        </div>
      </div>
      <p class="share-tip">本页 URL 可收藏或分享，直达此枚简牍。</p>
    </el-card>

    <el-dialog v-model="imgPreviewOpen" width="min(980px, 92vw)" class="img-dialog" append-to-body>
      <template #header>
        <div class="img-head">
          <span class="dj-heading img-title">影像预览 · {{ slip?.code }}</span>
          <div class="img-tools">
            <el-button size="small" @click="zoomOut">缩小</el-button>
            <el-button size="small" @click="zoomReset">还原</el-button>
            <el-button size="small" type="primary" plain @click="zoomIn">放大</el-button>
          </div>
        </div>
      </template>
      <div class="img-stage" @wheel.passive="onImgWheel">
        <img
          v-if="slip && slipImageSrc(slip.image_url)"
          :src="slipImageSrc(slip.image_url)"
          :alt="`简牍影像放大 ${slip.code}`"
          class="img-big"
          :style="{ transform: `scale(${imgScale})` }"
          draggable="false"
        />
      </div>
      <template #footer>
        <div class="img-foot">
          <span class="img-hint">提示：按住 Ctrl 再滚轮可缩放；可拖动滚动条查看细节。</span>
          <el-button @click="imgPreviewOpen = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 40px;
}
.back-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.back-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.back-kicker {
  margin-bottom: 0;
  font-size: 10px;
  letter-spacing: 0.36em;
}
.back-title {
  font-size: clamp(17px, 2.5vw, 20px);
  letter-spacing: 0.1em;
}
.main-card .title {
  margin: 0 0 8px;
  font-size: 22px;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.code {
  font-family: var(--dj-font-display);
  font-weight: 700;
  color: var(--el-color-primary);
}
.actions {
  display: flex;
  gap: 8px;
}
.reader-bar {
  margin: 10px 0 6px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: var(--dj-ink-soft);
  font-size: 12px;
}
.reader-lbl {
  font-family: var(--dj-font-display);
  letter-spacing: 0.1em;
  color: var(--dj-bamboo);
}
.reader-group :deep(.el-button) {
  font-size: 12px;
}
.sel-hint {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--dj-ink-soft);
}
.sel-hint::before {
  content: "";
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 8px;
  background: rgba(92, 107, 84, 0.55);
  vertical-align: 1px;
}
.meta {
  margin: 0 0 16px;
  color: var(--dj-ink-soft);
  font-size: 14px;
}
.anchor-bar {
  margin: -6px 0 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--dj-ink-soft);
}
.a-dot {
  color: rgba(201, 176, 138, 0.9);
  user-select: none;
}
.sec-anchor {
  height: 1px;
}
.body {
  margin: 0;
  white-space: pre-wrap;
  font-family: var(--dj-font-slip-reading, "Kaiti SC", "STKaiti", "KaiTi", "FangSong", "STFangsong", serif);
  font-feature-settings: "kern" 1;
  letter-spacing: 0.04em;
  line-height: 1.82;
  font-size: 13px;
  font-weight: 400;
  color: var(--dj-ink);
}
html.dark .body {
  color: rgba(252, 246, 234, 0.94);
}
.tags {
  margin-top: 16px;
  font-size: 13px;
  color: var(--dj-bamboo);
}
.share-tip {
  margin-top: 20px;
  font-size: 12px;
  color: var(--dj-ink-soft);
}
.rag-on-slip {
  margin-top: 22px;
  padding: 16px 18px;
  border-radius: 10px;
  border: 1px solid rgba(110, 88, 58, 0.14);
  background: rgba(255, 252, 246, 0.85);
}
.rag-title {
  margin: 0 0 8px;
  font-size: 16px;
}
.rag-hint {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--dj-ink-soft);
}
.rag-hint code {
  font-size: 11px;
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(239, 226, 204, 0.5);
}
.rag-actions {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}
.rag-samples {
  margin: 0 0 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.rag-samples-label {
  font-size: 12px;
  color: var(--dj-ink-soft);
  letter-spacing: 0.04em;
  flex-shrink: 0;
}
.rag-samples-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.sample-chip {
  cursor: pointer;
  max-width: 100%;
}
.rag-tip {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--dj-ink-soft);
}
.rag-tip strong {
  color: var(--dj-seal);
  font-weight: 600;
}
.stream-sw {
  margin-right: auto;
}
.rag-status {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--dj-ink-soft);
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.rag-status .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(154, 52, 18, 0.55);
  animation: dj-breathe-dot 1.1s ease-in-out infinite;
}
.rag-answer {
  margin-top: 16px;
  padding-top: 16px;
  border-top: none;
}
.rag-answer.dj-answer-surface {
  padding-top: 16px;
}
.answer-label {
  margin: 12px 0 8px;
  font-size: 14px;
}
.answer-label:first-child {
  margin-top: 0;
}
.answer-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.ans-actions {
  display: inline-flex;
  gap: 8px;
  flex-wrap: wrap;
}
.refs-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-top: 12px;
}
.refs-actions {
  display: inline-flex;
  align-items: baseline;
  gap: 10px;
}
.refs-title {
  margin: 0;
}
.refs-toggle {
  font-size: 12px;
  padding: 0;
}
.refs-copy {
  font-size: 12px;
  padding: 0;
}
.answer-body {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.75;
  font-size: 14px;
  color: var(--dj-ink);
  word-break: break-word;
}
.stream-caret {
  display: inline-block;
  width: 8px;
  height: 1.05em;
  margin-left: 4px;
  border-radius: 2px;
  background: rgba(154, 52, 18, 0.55);
  vertical-align: -0.12em;
  animation: dj-caret-breathe 0.95s ease-in-out infinite;
}

@keyframes dj-caret-breathe {
  0%,
  100% {
    opacity: 0.18;
  }
  50% {
    opacity: 0.7;
  }
}

@keyframes dj-breathe-dot {
  0%,
  100% {
    opacity: 0.25;
    transform: scale(0.9);
  }
  50% {
    opacity: 0.75;
    transform: scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .rag-status .dot {
    animation: none;
    opacity: 0.5;
  }
  .stream-caret {
    animation: none;
    opacity: 0.35;
  }
}
.ref-list {
  margin: 0;
  padding-left: 1.2em;
  font-size: 13px;
  line-height: 1.55;
}
.ref-link {
  color: var(--el-color-primary);
}
.ref-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.ref-via {
  font-size: 12px;
  color: var(--dj-ink-soft);
}
.ref-expand {
  border: 0;
  background: transparent;
  color: var(--dj-seal, #9a3412);
  cursor: pointer;
  font-size: 12px;
  padding: 0;
}
.ref-quote {
  margin: 6px 0 8px;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  max-height: 220px;
  overflow: auto;
}
.guess-box {
  margin-top: 22px;
  padding: 16px 18px;
  border-radius: var(--dj-radius-sm, 10px);
  border: 1px solid rgba(201, 176, 138, 0.38);
  background: linear-gradient(
    145deg,
    rgba(255, 252, 245, 0.9) 0%,
    rgba(239, 226, 204, 0.35) 100%
  );
  box-shadow: 0 2px 14px rgba(42, 34, 24, 0.04);
}
.guess-title {
  margin: 0 0 6px;
  font-size: 16px;
}
.guess-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 2px;
}
.guess-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--dj-ink-soft);
  line-height: 1.55;
}
.guess-chips {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.guess-btn {
  text-align: left;
  height: auto;
  white-space: normal;
  line-height: 1.45;
}
.figure {
  position: relative;
  margin: 16px 0;
  text-align: center;
  padding: 10px 18px;
  border-radius: 10px;
  border: 1px solid rgba(139, 90, 43, 0.22);
  background: linear-gradient(180deg, rgba(255, 251, 243, 0.9), rgba(212, 165, 116, 0.14));
  box-shadow: 0 6px 22px rgba(62, 58, 57, 0.06);
}
.rope {
  position: absolute;
  top: 10px;
  bottom: 10px;
  width: 18px;
  pointer-events: none;
  opacity: 0.75;
  background: url("/patterns/bamboo-rope.svg") repeat-y;
  background-size: 18px 120px;
  filter: drop-shadow(0 1px 0 rgba(255, 255, 255, 0.35));
}
.rope-left {
  left: 10px;
}
.rope-right {
  right: 10px;
}
.slip-img {
  max-width: 100%;
  max-height: min(70vh, 720px);
  width: auto;
  height: auto;
  border: 1px solid var(--dj-border-light);
  border-radius: 6px;
  background: #2a2218;
  object-fit: contain;
  cursor: zoom-in;
}
.img-cap {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--dj-ink-soft);
}

html.dark .figure {
  background: linear-gradient(180deg, rgba(36, 32, 25, 0.75), rgba(26, 23, 18, 0.55));
  border-color: rgba(74, 67, 56, 0.85);
}
html.dark .rope {
  opacity: 0.45;
}

.img-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
}
.img-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.img-title {
  font-size: 15px;
  letter-spacing: 0.1em;
}
.img-tools {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.img-stage {
  max-height: min(70vh, 720px);
  overflow: auto;
  border-radius: 10px;
  border: 1px solid rgba(201, 176, 138, 0.35);
  background: rgba(42, 34, 24, 0.88);
  padding: 10px;
}
.img-big {
  display: block;
  margin: 0 auto;
  max-width: 100%;
  max-height: 100%;
  transform-origin: top center;
  transition: transform 0.12s ease;
  user-select: none;
}
.img-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.img-hint {
  font-size: 12px;
  color: var(--dj-ink-soft);
}

@media (prefers-reduced-motion: reduce) {
  .img-big {
    transition: none;
  }
}
</style>
