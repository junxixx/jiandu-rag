<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";
import { getRagHistory, pushRagQuestion, clearRagHistory } from "@/composables/ragHistory";
import { trackEvent } from "@/composables/track";
import { pushRagStep, readRagEventStream, refLabel, refQuote, type RagStep } from "@/composables/ragStream";
import RagStatusSteps from "@/components/rag/RagStatusSteps.vue";
import HomeSlipRecCard from "@/components/home/HomeSlipRecCard.vue";
import HomeHeroFloatingSlips from "@/components/home/HomeHeroFloatingSlips.vue";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const tourOpen = ref(false);

type HomeSlipCard = {
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

const hot = ref<HomeSlipCard[]>([]);
const forYou = ref<HomeSlipCard[]>([]);
const recLoading = ref(false);
const dailyLoading = ref(false);
const daily = ref<{ date: string; slip: { id: number; code: string; title: string; site_name: string | null; era: string | null } } | null>(
  null
);
const question = ref("");
const ragAnswer = ref("");
const ragRefs = ref<Array<Record<string, unknown>>>([]);
const ragLoading = ref(false);
const ragHistory = ref<string[]>([]);
const useStreamRag = ref(true);
const showRagRefs = ref(false);
const ragSteps = ref<RagStep[]>([]);
const refOpen = ref<Record<number, boolean>>({});
const sampleQs = [
  "此简中某词作何解？在当时制度中如何使用？",
  "释文与绎白的关键差异在哪里？可否逐句指出？",
  "此简涉及何种文书体例（爰书/簿籍/禀食等）？依据何在？",
];
/** 呈问按钮短时墨迹晕开 */
const askSplash = ref(false);
function triggerAskSplash() {
  askSplash.value = true;
  window.setTimeout(() => {
    askSplash.value = false;
  }, 900);
}
/** 从外链 ?slip= 带入时，问牍附带 slip_id（与本牍上下文一致） */
const ragSlipFocus = ref<number | null>(null);

const topics = ref<Array<{ id: number; name: string; description?: string | null; hot?: number }>>([]);
const characters = ref<Array<{ role_key: string; title: string; hint: string; path: string }>>([]);
const itemcfSlips = ref<HomeSlipCard[]>([]);
const graphRelSlips = ref<HomeSlipCard[]>([]);
const activeRecTab = ref<"hot" | "for_you" | "topics" | "roles">("hot");

const shortcuts = [
  { title: "牍库", desc: "检索编号与释文", to: "/browse", icon: "Collection" },
  { title: "每日一牍", desc: "日课与快读", to: "/daily", icon: "Calendar" },
  { title: "简牍图谱", desc: "人物与遗址编联", to: "/graph", icon: "Share" },
  { title: "边塞夜话", desc: "历史人物与边塞身份夜话", to: "/chat", icon: "ChatDotRound" },
  { title: "辩论社", desc: "AI 驳难", to: "/debate", icon: "ChatLineSquare" },
  { title: "戍边手记", desc: "剧情线引导", to: "/quests", icon: "Notebook" },
];

function goShortcut(to: string) {
  if (to === "/chat" && !auth.token) {
    router.push({ name: "login", query: { redirect: "/chat" } });
    return;
  }
  router.push(to);
}

function refreshHistory() {
  ragHistory.value = getRagHistory();
}

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

async function loadRec() {
  recLoading.value = true;
  try {
    const { data } = await http.get("/recommend/home");
    hot.value = (data.hot || []) as HomeSlipCard[];
    forYou.value = (data.for_you || []) as HomeSlipCard[];
    topics.value = data.topics || [];
    characters.value = data.characters || [];
    itemcfSlips.value = (data.itemcf_slips || []) as HomeSlipCard[];
    graphRelSlips.value = (data.graph_related_slips || []) as HomeSlipCard[];
  } finally {
    recLoading.value = false;
  }
}

async function loadDaily() {
  dailyLoading.value = true;
  try {
    const { data } = await http.get("/daily-slip/today");
    daily.value = {
      date: String(data.date || ""),
      slip: {
        id: Number(data.slip?.id),
        code: String(data.slip?.code || ""),
        title: String(data.slip?.title || ""),
        site_name: (data.slip?.site_name as string | null) || null,
        era: (data.slip?.era as string | null) || null,
      },
    };
  } catch {
    daily.value = null;
  } finally {
    dailyLoading.value = false;
  }
}

function scrollToRag() {
  document.getElementById("tour-rag")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function useSample(q: string) {
  question.value = q;
  document.getElementById("tour-rag")?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function onAskKeydown(e: KeyboardEvent) {
  if (e.key !== "Enter") return;
  // Shift+Enter = 换行；Enter = 提交
  if ((e as any).isComposing) return;
  if (e.shiftKey) return;
  e.preventDefault();
  void askRag();
}

function copyHomeRagRefsList() {
  const refs = ragRefs.value || [];
  if (!refs.length) {
    ElMessage.info("暂无可复制的引用清单");
    return;
  }
  const lines = refs.map((r) => `- ${formatRef(r)}`);
  navigator.clipboard.writeText(["【所据简牍清单】", ...lines].join("\n")).then(
    () => ElMessage.success("已复制引用清单"),
    () => ElMessage.error("复制失败")
  );
}

type CopyMode = "plain" | "md" | "md_quote";
function _homeRefLine(r: Record<string, unknown>, mode: CopyMode): string {
  const label = formatRef(r);
  const rid = typeof r.id === "number" ? r.id : null;
  if ((mode === "md" || mode === "md_quote") && rid != null) return `- [${label}](/slip/${rid})`;
  return `- ${label}`;
}

function _homeUniqueSortedRefs(refs: Array<Record<string, unknown>>): Array<Record<string, unknown>> {
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

function copyHomeRagRefsListByMode(mode: CopyMode) {
  const refs = _homeUniqueSortedRefs(ragRefs.value || []);
  if (!refs.length) {
    ElMessage.info("暂无可复制的引用清单");
    return;
  }
  const lines = refs.map((r) => _homeRefLine(r, mode));
  const text = ["【所据简牍清单】", ...lines].join("\n");
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

function copyHomeRagQuoteBlock(mode: CopyMode) {
  const ans = (ragAnswer.value || "").trim();
  const refs = _homeUniqueSortedRefs(ragRefs.value || []);
  const q = (question.value || "").trim();
  if (!ans) {
    ElMessage.info("暂无可复制的绎读内容");
    return;
  }
  const lines: string[] = [];
  lines.push("【引用块｜问牍绎读】");
  lines.push("——");
  if (q) {
    lines.push(`问题：${q}`);
    lines.push("");
  }
  lines.push(ans);
  if (refs.length) {
    lines.push("");
    lines.push("【所据简牍】");
    lines.push(...refs.map((r) => _homeRefLine(r, mode)));
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

async function askRag() {
  if (!question.value.trim()) return;
  triggerAskSplash();
  showRagRefs.value = false;
  refOpen.value = {};
  if (useStreamRag.value) {
    await askRagStream();
    return;
  }
  ragLoading.value = true;
  ragAnswer.value = "";
  ragRefs.value = [];
  ragSteps.value = [{ stage: "retrieve", message: "正在检索简牍" }];
  try {
    const payload: { question: string; slip_id?: number } = { question: question.value };
    if (ragSlipFocus.value != null) payload.slip_id = ragSlipFocus.value;
    const { data } = await http.post("/rag/query", payload);
    ragAnswer.value = data.answer;
    ragRefs.value = data.references || [];
    showRagRefs.value = ragRefs.value.length > 0;
    const steps = (data.rag_meta?.steps || []) as RagStep[];
    if (steps.length) ragSteps.value = steps;
    pushRagQuestion(question.value);
    refreshHistory();
    trackEvent("rag_query", { q_len: question.value.length, refused: Boolean(data.refused) });
  } catch {
    ElMessage.error("牍师暂未能作答，请稍后再试");
  } finally {
    ragLoading.value = false;
  }
}

async function askRagStream() {
  const q = question.value.trim();
  triggerAskSplash();
  ragLoading.value = true;
  ragAnswer.value = "";
  ragRefs.value = [];
  ragSteps.value = [];
  showRagRefs.value = false;
  refOpen.value = {};
  try {
    const streamBody: { question: string; slip_id?: number } = { question: q };
    if (ragSlipFocus.value != null) streamBody.slip_id = ragSlipFocus.value;
    const res = await fetch("/api/rag/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(streamBody),
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
    pushRagQuestion(q);
    refreshHistory();
    trackEvent("rag_query", { q_len: q.length, stream: true });
  } catch {
    ElMessage.error("流式问牍失败，可改非流式重试");
  } finally {
    ragLoading.value = false;
  }
}

function useHistoryItem(q: string) {
  question.value = q;
}

function clearHistory() {
  clearRagHistory();
  refreshHistory();
  ElMessage.success("已清空问牍记录");
}

function closeTour() {
  localStorage.setItem("dj_tour_v1", "1");
}

function replayTour() {
  tourOpen.value = true;
}

function colTourId(to: string): string | undefined {
  if (to === "/browse") return "tour-browse";
  if (to === "/daily") return "tour-daily";
  return undefined;
}

onMounted(async () => {
  loadRec();
  loadDaily();
  refreshHistory();
  const q = { ...route.query } as Record<string, string | string[] | undefined>;
  const rawAsk = q.ask;
  const askStr = Array.isArray(rawAsk) ? rawAsk[0] : rawAsk;
  const rawSlip = q.slip;
  const slipStr = Array.isArray(rawSlip) ? rawSlip[0] : rawSlip;
  if (slipStr != null && /^\d+$/.test(String(slipStr).trim())) {
    ragSlipFocus.value = Number(String(slipStr).trim());
    delete q.slip;
  }
  const fromSlipGuess = typeof askStr === "string" && askStr.trim().length > 0;
  if (fromSlipGuess) {
    question.value = askStr.trim();
    delete q.ask;
    router.replace({ query: q });
  } else if (ragSlipFocus.value != null) {
    router.replace({ query: q });
  }
  await nextTick();
  if (fromSlipGuess) {
    await nextTick();
    document.getElementById("tour-rag")?.scrollIntoView({ behavior: "smooth", block: "center" });
    await askRag();
    trackEvent("rag_from_slip_guess", { q_len: question.value.length });
  }
  if (!localStorage.getItem("dj_tour_v1") && !fromSlipGuess) {
    tourOpen.value = true;
  }
});
</script>

<template>
  <div class="page dj-page">
    <HomeHeroFloatingSlips />
    <div class="dj-page__surface">
    <el-alert
      v-if="!auth.token"
      title="登录后可记入掌阅、夜话烽燧、领取功课积分；未登录亦可浏览牍库、问牍与雅集。"
      type="info"
      :closable="false"
      class="banner"
      show-icon
    />

    <section class="hero dj-slip-card dj-anim-in dj-anim-in--soft">
      <div class="hero-ambient" aria-hidden="true">
        <span class="orb orb-seal" />
        <span class="orb orb-bamboo" />
        <span class="orb orb-gold" />
      </div>
      <div class="hero-grid">
        <div class="hero-main">
          <div class="seal" aria-hidden="true">简</div>
          <span class="dj-kicker hero-kicker">问牍·青声 · 书斋</span>
          <h1>简牍遗文 · 青年共读</h1>
          <p class="lead">
            自边塞烽燧至乡里簿籍，以<strong>万卷牍库</strong>为舟、<strong>人物编联</strong>为缆；或向「牍师」问疑，或与戍卒夜话，或在雅集击节——令千年墨迹，化作今日同窗。
          </p>
          <p class="lead lead-sub">
            在此可一日一牍养习、一图一链识人、一问一绎解惑；路径各异，同归「读牍」一事，纸轻墨淡，意重声长。
          </p>
          <div class="hero-actions">
            <el-button size="small" round type="primary" aria-label="立即前往问牍" @click="scrollToRag">立即问牍</el-button>
            <el-button size="small" round plain type="primary" aria-label="重新播放新手引导" @click="replayTour">
              重温指引
            </el-button>
          </div>
        </div>

        <aside class="hero-aside">
          <el-card class="today-card today-scroll dj-slip-card" shadow="hover">
            <template #header>
              <span class="card-h">今日一牍</span>
              <span v-if="daily?.date" class="today-date">{{ daily.date }}</span>
            </template>
            <el-skeleton v-if="dailyLoading" :rows="3" animated />
            <template v-else-if="daily">
              <p class="today-code">{{ daily.slip.code }}</p>
              <p class="today-title">{{ daily.slip.title }}</p>
              <p v-if="daily.slip.site_name || daily.slip.era" class="today-meta">
                <span v-if="daily.slip.site_name">{{ daily.slip.site_name }}</span>
                <span v-if="daily.slip.era">{{ daily.slip.era }}</span>
              </p>
              <div class="today-actions">
                <el-button size="small" type="primary" plain @click="router.push('/daily')">去日课</el-button>
                <el-button size="small" @click="router.push('/slip/' + daily.slip.id)">展卷</el-button>
              </div>
            </template>
            <template v-else>
              <el-empty description="尚未排定今日简牍" />
            </template>
          </el-card>
        </aside>
      </div>
    </section>

    <header class="dj-section-head dj-anim-in">
      <span class="dj-section-head__kicker">由浅入深</span>
      <h2 class="dj-section-head__title">入门六径</h2>
      <p class="dj-section-head__sub">自牍库检索、日课、图谱、夜话至辩论与手记，六条路径各取所需，亦可交叉而行。</p>
    </header>
    <el-row :gutter="12" class="shortcuts">
      <el-col
        v-for="(s, idx) in shortcuts"
        :key="s.to"
        :xs="12"
        :sm="8"
        :md="8"
        :id="colTourId(s.to)"
        class="stagger"
        :style="{ animationDelay: `${Math.min(idx, 8) * 70}ms` }"
      >
        <div
          class="scard dj-slip-card"
          role="button"
          tabindex="0"
          :aria-label="`进入${s.title}`"
          @click="goShortcut(s.to)"
          @keydown.enter.prevent="goShortcut(s.to)"
        >
          <el-icon class="scicon" :size="26">
            <component :is="s.icon" />
          </el-icon>
          <div class="sctitle">{{ s.title }}</div>
          <div class="scdesc">{{ s.desc }}</div>
        </div>
      </el-col>
    </el-row>

    <section class="rec-zone dj-anim-in">
      <header class="dj-section-head">
        <span class="dj-section-head__kicker">为你备卷</span>
        <h2 class="dj-section-head__title">今日可读</h2>
        <p class="dj-section-head__sub">热点、为你（含同好/编联）、话题与夜话角色；切换页签即可浏览。</p>
      </header>

      <el-card class="dj-slip-card rec-card" shadow="hover">
        <el-tabs v-model="activeRecTab" class="rec-tabs">
          <el-tab-pane label="热点" name="hot" />
          <el-tab-pane label="为你" name="for_you" />
          <el-tab-pane label="话题" name="topics" />
          <el-tab-pane label="夜话" name="roles" />
        </el-tabs>

        <el-skeleton v-if="recLoading" :rows="6" animated />

        <template v-else>
          <template v-if="activeRecTab === 'hot'">
            <el-empty v-if="!hot.length" description="尚无热点；可先导入简牍数据，或去牍库随意展卷。" />
            <ul v-else class="rec-slip-grid">
              <HomeSlipRecCard v-for="s in hot" :key="s.id" :slip="s" :show-heat="true" />
            </ul>
          </template>

          <template v-else-if="activeRecTab === 'for_you'">
            <div v-if="!forYou.length && !itemcfSlips.length && !graphRelSlips.length" class="for-you-empty">
              <el-empty description="登录后多读几枚简牍；同好共读与编联延伸将随读牍习惯出现。" />
            </div>
            <div v-else class="for-you-stack">
              <template v-if="forYou.length">
                <h3 class="rec-subhead">为你推荐</h3>
                <ul class="rec-slip-grid">
                  <HomeSlipRecCard v-for="s in forYou" :key="'fy-' + s.id" :slip="s" :show-heat="true" />
                </ul>
              </template>
              <template v-if="itemcfSlips.length">
                <h3 class="rec-subhead">同好共读</h3>
                <p class="rec-subhint">依你展卷习惯，荐相近体裁与主题之牍。</p>
                <ul class="rec-slip-grid">
                  <HomeSlipRecCard v-for="s in itemcfSlips" :key="'ic-' + s.id" :slip="s" :show-heat="false" />
                </ul>
              </template>
              <template v-if="graphRelSlips.length">
                <h3 class="rec-subhead">编联延伸</h3>
                <p class="rec-subhint">依人物、遗址、标签与语料节点编联，延伸可读之牍。</p>
                <ul class="rec-slip-grid">
                  <HomeSlipRecCard v-for="s in graphRelSlips" :key="'gr-' + s.id" :slip="s" :show-heat="false" />
                </ul>
              </template>
            </div>
          </template>

          <template v-else-if="activeRecTab === 'topics'">
            <el-empty v-if="!topics.length" description="话题榜暂空；可先去雅集发起一帖，题目从牍库来。" />
            <ul v-else class="list">
              <li v-for="t in topics" :key="t.id">
                <router-link class="row-link" to="/forum">
                  <span class="code">#</span>
                  <span class="title">{{ t.name }}</span>
                  <span v-if="t.description" class="meta">{{ t.description }}</span>
                </router-link>
              </li>
            </ul>
          </template>

          <template v-else-if="activeRecTab === 'roles'">
            <el-empty v-if="!characters.length" description="夜话角色尚未配置；可在后端补齐角色卡片。" />
            <ul v-else class="list">
              <li v-for="c in characters" :key="c.role_key">
                <router-link class="row-link" :to="c.path">
                  <span class="code">夜</span>
                  <span class="title">{{ c.title }}</span>
                  <span class="meta">{{ c.hint }}</span>
                </router-link>
              </li>
            </ul>
          </template>

        </template>
      </el-card>
    </section>

    <el-card id="tour-rag" class="rag dj-slip-card rag-card rag-card--spotlight dj-anim-in" shadow="hover">
      <template #header>
        <span class="rag-head-title">问牍</span>
        <span class="header-sub">关键词与向量融合检索；材料不足会改写再检，仍不足则拒答。所引简牍可展开释文核对。</span>
      </template>
      <div class="rag-samples">
        <span class="rag-samples-label">示例问法：</span>
        <div class="rag-samples-chips">
          <el-tag
            v-for="(s, i) in sampleQs"
            :key="i"
            size="small"
            class="chip sample-chip"
            effect="plain"
            round
            @click="useSample(s)"
          >
            {{ s }}
          </el-tag>
        </div>
      </div>
      <el-input
        v-model="question"
        type="textarea"
        :rows="2"
        placeholder="例如：「禀食」简与戍卒口粮有何关系？"
        aria-label="问牍输入框"
        @keydown="onAskKeydown"
      />
      <p class="rag-tip">
        小贴士：若问题里包含<strong>编号</strong>、<strong>地名</strong>、<strong>制度词</strong>（如“禀食”“爰书”“候长”），检索更准。
      </p>
      <div class="rag-actions">
        <el-switch v-model="useStreamRag" active-text="逐字呈献" inactive-text="全篇呈览" class="stream-sw" />
        <el-button type="primary" :loading="ragLoading" :class="{ 'rag-ask-splash': askSplash }" @click="askRag">
          呈问
        </el-button>
        <router-link class="link-more" to="/about">不了解能问什么？见「关于」页</router-link>
      </div>
      <RagStatusSteps :steps="ragSteps" :live="ragLoading" />

      <div v-if="ragHistory.length" class="hist">
        <div class="hist-head">
          <span>近次所问（仅本机）</span>
          <el-button text type="danger" size="small" @click="clearHistory">清空</el-button>
        </div>
        <div class="chips">
          <el-tag
            v-for="(h, i) in ragHistory"
            :key="i"
            class="chip"
            effect="plain"
            @click="useHistoryItem(h)"
          >
            {{ h.length > 36 ? h.slice(0, 36) + "…" : h }}
          </el-tag>
        </div>
      </div>

      <div v-if="ragLoading || ragAnswer" class="answer dj-answer-surface">
        <h4 class="dj-heading answer-h">绎读</h4>
        <el-skeleton v-if="ragLoading && !ragAnswer" :rows="4" animated class="rag-skel" />
        <p v-else class="pre">
          {{ ragAnswer }}<span v-if="ragLoading && useStreamRag" class="stream-caret" aria-hidden="true" />
        </p>
        <template v-if="ragRefs.length">
          <div class="refs-head">
            <h4 class="dj-heading answer-h refs-title">所据简牍</h4>
            <div class="refs-actions">
              <el-button text type="primary" class="refs-toggle" @click="showRagRefs = !showRagRefs">
                {{ showRagRefs ? "收起" : `展开（${ragRefs.length}）` }}
              </el-button>
              <el-dropdown trigger="click">
                <el-button text type="primary" class="refs-copy">复制清单</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="copyHomeRagRefsListByMode('plain')">普通列表</el-dropdown-item>
                    <el-dropdown-item @click="copyHomeRagRefsListByMode('md')">论坛 Markdown（带链接）</el-dropdown-item>
                    <el-dropdown-item @click="copyHomeRagRefsListByMode('md_quote')">论坛引用（>）+ 链接</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-dropdown trigger="click">
                <el-button text type="primary" class="refs-copy">复制引用块</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="copyHomeRagQuoteBlock('plain')">普通文本</el-dropdown-item>
                    <el-dropdown-item @click="copyHomeRagQuoteBlock('md')">论坛 Markdown（带链接）</el-dropdown-item>
                    <el-dropdown-item @click="copyHomeRagQuoteBlock('md_quote')">论坛引用（>）+ 链接</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <el-collapse-transition>
            <ul v-show="showRagRefs" class="ref-list ref-list--slips">
              <li v-for="(r, i) in ragRefs" :key="i" class="ref-slip">
                <span class="ref-no" aria-hidden="true">{{ String(i + 1).padStart(2, "0") }}</span>
                <div class="ref-body">
                  <div class="ref-line">
                    <router-link v-if="typeof r.id === 'number'" class="ref-link" :to="'/slip/' + r.id">
                      {{ refLabel(r) }}
                    </router-link>
                    <span v-else class="ref-plain">{{ refLabel(r) }}</span>
                    <span v-if="r.via" class="ref-via">{{ r.via }}</span>
                    <button type="button" class="ref-expand" @click="toggleRef(i)">
                      {{ refOpen[i] ? "收起释文" : "展开释文" }}
                    </button>
                  </div>
                  <pre v-if="refOpen[i]" class="ref-quote">{{ refQuote(r) }}</pre>
                </div>
              </li>
            </ul>
          </el-collapse-transition>
        </template>
      </div>
    </el-card>

    <el-tour v-model="tourOpen" @close="closeTour" @finish="closeTour">
      <el-tour-step
        target="#tour-browse"
        title="牍库"
        description="在此按编号、释文检索简牍，打开详情页可分享链接、记入掌阅。"
        placement="bottom"
      />
      <el-tour-step
        target="#tour-daily"
        title="每日一牍"
        description="每日一枚释文与绎白，配合日课题目，养成读牍节奏。"
        placement="bottom"
      />
      <el-tour-step
        target="#tour-rag"
        title="问牍"
        description="据牍库材料智能问答，所引简牍可点入详情展卷。"
        placement="top"
      />
    </el-tour>
    </div>
  </div>
</template>

<style scoped>
.page {
  position: relative;
  isolation: isolate;
  padding-bottom: 48px;
}
.dj-page__surface {
  position: relative;
  z-index: 1;
}
.stagger {
  animation: dj-stagger-in 0.58s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.banner {
  margin-bottom: 20px;
  border-radius: var(--dj-radius-sm, 10px);
  border: 1px solid rgba(201, 176, 138, 0.35);
}
.hero {
  position: relative;
  padding: 36px 36px 34px 44px;
  margin-bottom: 8px;
  background:
    radial-gradient(ellipse 90% 70% at 100% 0%, rgba(154, 52, 18, 0.07), transparent 55%),
    radial-gradient(ellipse 60% 50% at 0% 100%, rgba(92, 107, 84, 0.06), transparent 50%),
    linear-gradient(
      145deg,
      rgba(255, 251, 243, 0.97) 0%,
      rgba(252, 246, 234, 0.9) 42%,
      rgba(239, 226, 204, 0.42) 100%
    );
  border: 1px solid rgba(201, 176, 138, 0.42);
  border-radius: var(--dj-radius, 14px);
  box-shadow:
    var(--dj-shadow-card, 0 4px 24px rgba(42, 34, 24, 0.07)),
    inset 0 1px 0 rgba(255, 255, 255, 0.65);
}
.hero-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 18px;
  align-items: start;
}
.hero-main {
  min-width: 0;
}
.hero-actions {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.hero-aside {
  min-width: 0;
}
/* 今日一牍：卷轴木轴感（内嵌，避免被卡片 overflow 裁切）+ 自右侧入场 */
.today-scroll {
  position: relative;
  animation: dj-today-roll-in 0.75s cubic-bezier(0.22, 1, 0.36, 1) both;
  box-shadow:
    var(--dj-shadow-card, 0 4px 24px rgba(62, 58, 57, 0.07)),
    inset 10px 0 0 -2px rgba(107, 74, 42, 0.14),
    inset -10px 0 0 -2px rgba(107, 74, 42, 0.14);
}
@keyframes dj-today-roll-in {
  from {
    opacity: 0;
    transform: translateX(36px);
    box-shadow: 0 2px 8px rgba(62, 58, 57, 0.04);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
.today-card :deep(.el-card__header) {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.today-date {
  font-size: 12px;
  color: var(--dj-bamboo);
  letter-spacing: 0.08em;
  opacity: 0.92;
  white-space: nowrap;
}
.today-code {
  margin: 0 0 6px;
  font-family: var(--dj-font-display);
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--el-color-primary);
}
.today-title {
  margin: 0 0 8px;
  line-height: 1.6;
  color: var(--dj-ink);
  font-size: 14px;
}
.today-meta {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--dj-ink-soft);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.today-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.hero-ambient {
  position: absolute;
  inset: -24px -18px -18px -18px;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}
.orb {
  position: absolute;
  border-radius: 50%;
  opacity: 0.18;
  filter: blur(0.5px);
  transform: translate3d(0, 0, 0);
}
.orb-seal {
  width: min(360px, 58vw);
  height: min(360px, 58vw);
  top: -18%;
  right: -12%;
  background: radial-gradient(circle, rgba(154, 52, 18, 0.55), transparent 68%);
  animation: dj-orb-drift 22s ease-in-out infinite;
}
.orb-bamboo {
  width: min(300px, 50vw);
  height: min(300px, 50vw);
  bottom: -18%;
  left: -10%;
  background: radial-gradient(circle, rgba(92, 107, 84, 0.5), transparent 70%);
  animation: dj-orb-drift 18s ease-in-out infinite;
  animation-delay: -8s;
}
.orb-gold {
  width: min(240px, 42vw);
  height: min(240px, 42vw);
  left: 48%;
  top: 42%;
  background: radial-gradient(circle, rgba(166, 124, 82, 0.42), transparent 70%);
  animation: dj-orb-drift 26s ease-in-out infinite;
  animation-delay: -14s;
}
.hero-kicker {
  margin-bottom: 6px;
}
.seal {
  position: absolute;
  right: 24px;
  top: 20px;
  width: 56px;
  height: 56px;
  border: 2px solid rgba(154, 52, 18, 0.35);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--dj-font-display);
  font-size: 26px;
  color: rgba(154, 52, 18, 0.45);
  transform: rotate(-6deg);
  pointer-events: none;
  animation: dj-seal-float 4.2s ease-in-out infinite;
}
.hero h1 {
  font-size: clamp(22px, 4vw, 30px);
  margin: 0 0 14px;
  padding-right: 80px;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.lead {
  margin: 0 0 12px;
  line-height: 1.92;
  color: var(--dj-ink-soft);
  font-size: 15px;
  max-width: 52em;
}
.lead-sub {
  margin: 0 0 18px;
  font-size: 14px;
  line-height: 1.88;
  color: var(--dj-ink-soft);
  opacity: 0.96;
  max-width: 48em;
  border-left: 3px solid rgba(124, 58, 33, 0.2);
  padding-left: 14px;
}
.lead strong {
  color: var(--dj-seal);
  font-weight: 600;
}
.shortcuts {
  margin-bottom: 32px;
}
.card-h {
  letter-spacing: 0.12em;
}
.card-rec :deep(.el-card__header) {
  font-size: 15px;
}
.rag-card :deep(.el-card__header) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.rag-head-title {
  font-size: 16px;
  letter-spacing: 0.14em;
}
.scard {
  padding: 20px 18px 18px;
  margin-bottom: 12px;
  border-radius: var(--dj-radius-sm, 10px);
  border: 1px solid rgba(201, 176, 138, 0.48);
  background: linear-gradient(
    168deg,
    rgba(255, 251, 243, 0.98) 0%,
    rgba(252, 246, 234, 0.82) 55%,
    rgba(239, 226, 204, 0.25) 100%
  );
  cursor: pointer;
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
  min-height: 128px;
  box-shadow: 0 2px 12px rgba(42, 34, 24, 0.04);
}
.scard:hover {
  transform: translateY(-4px);
  box-shadow: var(--dj-shadow-card-hover, 0 12px 40px rgba(42, 34, 24, 0.1));
  border-color: rgba(166, 124, 82, 0.42);
}
.scicon {
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
.sctitle {
  font-family: var(--dj-font-display);
  font-weight: 600;
  font-size: 16px;
  color: var(--dj-ink);
  margin-bottom: 4px;
}
.scdesc {
  font-size: 12px;
  color: var(--dj-ink-soft);
  line-height: 1.5;
}
.row-rec {
  margin-bottom: 8px;
}
.rec-zone {
  margin-top: 8px;
  margin-bottom: 6px;
}
.rec-card {
  margin-top: 10px;
}
.rec-tabs {
  margin: -6px 0 10px;
}
.rec-card :deep(.el-tabs__header) {
  margin: 0 0 10px;
}
.rec-card :deep(.el-tabs__nav-wrap::after) {
  background-color: rgba(201, 176, 138, 0.35);
}
.rec-card :deep(.el-tabs__active-bar) {
  background: linear-gradient(90deg, var(--dj-seal), var(--dj-gold));
}
.rec-card :deep(.el-tabs__item) {
  font-family: var(--dj-font-display);
  letter-spacing: 0.12em;
  color: var(--dj-ink-soft);
}
.rec-card :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
}
.rec-card :deep(.el-empty) {
  padding: 18px 0 10px;
}
.rec-slip-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
}
@media (min-width: 720px) {
  .rec-slip-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (min-width: 1024px) {
  .rec-slip-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
.for-you-stack {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.rec-subhead {
  margin: 0 0 10px;
  font-size: 15px;
  font-family: var(--dj-font-display);
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--dj-ink);
}
.rec-subhint {
  margin: -4px 0 10px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--dj-ink-soft);
}
.for-you-empty :deep(.el-empty) {
  padding: 18px 0 10px;
}
.list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.row-link {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  text-decoration: none;
  color: inherit;
  padding: 6px 10px 6px 12px;
  margin: -6px -10px;
  border-radius: 6px;
  transition: background 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
  position: relative;
}
.row-link:hover {
  background: linear-gradient(90deg, rgba(124, 58, 33, 0.075), rgba(124, 58, 33, 0.03) 40%, transparent 100%);
  box-shadow: inset 3px 0 0 rgba(154, 52, 18, 0.28);
}
.row-link::before {
  content: "";
  position: absolute;
  left: 6px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  border-radius: 2px;
  background: linear-gradient(180deg, rgba(154, 52, 18, 0.0), rgba(154, 52, 18, 0.35), rgba(166, 124, 82, 0.0));
  opacity: 0;
  transition: opacity 0.18s ease;
}
.row-link:hover::before {
  opacity: 1;
}
.list li {
  padding: 10px 0;
  border-bottom: 1px dashed var(--dj-border-light);
  font-size: 14px;
}
.list li:last-child {
  border-bottom: none;
}
.code {
  font-family: var(--dj-font-display);
  font-weight: 600;
  color: var(--el-color-primary);
  flex-shrink: 0;
}
.title {
  color: var(--dj-ink);
  flex: 1;
  min-width: 0;
}
.meta {
  font-size: 12px;
  color: var(--dj-bamboo);
}
.rag {
  margin-top: 20px;
}
.rag-card--spotlight {
  border-color: rgba(139, 90, 43, 0.38) !important;
  box-shadow:
    0 8px 36px rgba(62, 58, 57, 0.09),
    0 0 0 1px rgba(212, 165, 116, 0.35),
    inset 0 1px 0 rgba(255, 252, 248, 0.9) !important;
  background: linear-gradient(
    165deg,
    rgba(255, 252, 248, 0.98) 0%,
    rgba(245, 243, 239, 0.55) 42%,
    rgba(212, 165, 116, 0.12) 100%
  );
}
.rag-ask-splash {
  position: relative;
  overflow: visible;
}
.rag-ask-splash::after {
  content: "";
  position: absolute;
  inset: -6px -10px;
  border-radius: inherit;
  pointer-events: none;
  background: radial-gradient(circle at 45% 50%, rgba(62, 58, 57, 0.14) 0%, transparent 58%);
  animation: dj-ink-bloom 0.85s ease-out both;
}
@keyframes dj-ink-bloom {
  0% {
    opacity: 0.2;
    transform: scale(0.92);
  }
  55% {
    opacity: 0.55;
  }
  100% {
    opacity: 0;
    transform: scale(1.35);
  }
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
.header-sub {
  font-weight: 400;
  font-size: 12px;
  line-height: 1.55;
  color: var(--dj-ink-soft);
  letter-spacing: 0.03em;
  margin-left: 0;
  max-width: 52em;
}
.rag-actions {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
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
.rag-skel {
  margin-top: 6px;
}
.link-more {
  font-size: 13px;
}
.stream-sw {
  margin-right: 8px;
}
.mini-hint {
  font-size: 12px;
  color: var(--dj-ink-soft);
  margin: 0 0 8px;
}
.hist {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--dj-border-light);
}
.hist-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--dj-ink-soft);
  margin-bottom: 8px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  cursor: pointer;
  max-width: 100%;
}
.answer {
  margin-top: 20px;
  padding-top: 0;
  border-top: none;
}
.answer-h {
  margin: 14px 0 10px;
  font-size: 15px;
  letter-spacing: 0.06em;
}
.answer-h:first-child {
  margin-top: 0;
}
.refs-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-top: 14px;
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
.pre {
  white-space: pre-wrap;
  line-height: 1.85;
  color: var(--dj-ink);
  margin: 0;
  font-size: 15px;
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
.ref-list {
  margin: 0;
  padding-left: 0;
  list-style: none;
  color: var(--dj-ink-soft);
  line-height: 1.75;
  font-size: 14px;
}
.ref-list--slips .ref-slip {
  display: flex;
  gap: 12px;
  align-items: stretch;
  margin-bottom: 10px;
  padding: 10px 12px 10px 10px;
  border-radius: var(--dj-radius-xs);
  border: 1px solid rgba(139, 90, 43, 0.28);
  background: linear-gradient(180deg, rgba(255, 252, 248, 0.96), rgba(212, 165, 116, 0.12));
  box-shadow: inset 3px 0 0 rgba(139, 90, 43, 0.35);
}
.ref-list--slips .ref-slip:last-child {
  margin-bottom: 0;
}
.ref-no {
  flex-shrink: 0;
  min-width: 2.25em;
  padding: 4px 6px;
  font-family: var(--dj-font-display);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-align: center;
  color: var(--dj-seal-red);
  background: rgba(245, 243, 239, 0.95);
  border: 1px solid rgba(192, 76, 76, 0.28);
  border-radius: 4px;
  align-self: flex-start;
}
.ref-body {
  flex: 1;
  min-width: 0;
}
.ref-plain {
  color: var(--dj-ink);
}
.ref-link {
  color: var(--el-color-primary);
  text-decoration: underline;
  text-underline-offset: 3px;
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
  margin: 8px 0 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  max-height: 220px;
  overflow: auto;
  color: var(--dj-ink);
}

@keyframes dj-orb-drift {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(-16px, 18px) scale(1.06);
  }
}

@keyframes dj-seal-float {
  0%,
  100% {
    transform: rotate(-6deg) translateY(0);
  }
  50% {
    transform: rotate(-6deg) translateY(-3px);
  }
}

@keyframes dj-stagger-in {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .stagger {
    animation: none;
  }
  .today-scroll {
    animation: none;
  }
  .rag-ask-splash::after {
    animation: none;
    opacity: 0;
  }
  .orb-seal,
  .orb-bamboo,
  .orb-gold,
  .seal {
    animation: none;
  }
  .stream-caret {
    animation: none;
    opacity: 0.35;
  }
  .rag-status .dot {
    animation: none;
    opacity: 0.5;
  }
  .row-link,
  .row-link::before {
    transition: none;
  }
}

:global(html.dark) .row-link:hover {
  background: linear-gradient(90deg, rgba(196, 154, 98, 0.11), rgba(196, 154, 98, 0.04) 45%, transparent 100%);
  box-shadow: inset 3px 0 0 rgba(196, 154, 98, 0.32);
}
:global(html.dark) .row-link::before {
  background: linear-gradient(180deg, rgba(196, 154, 98, 0.0), rgba(196, 154, 98, 0.45), rgba(196, 154, 98, 0.0));
}

@media (max-width: 980px) {
  .hero {
    padding: 30px 22px 24px;
  }
  .hero-grid {
    grid-template-columns: 1fr;
  }
  .seal {
    right: 14px;
    top: 14px;
    width: 52px;
    height: 52px;
  }
}
</style>
