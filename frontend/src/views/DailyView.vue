<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";
import { slipImageSrc } from "@/composables/slipImage";

const auth = useAuthStore();
const slip = ref<Record<string, unknown> | null>(null);
const funFact = ref<string | null>(null);
const quizzes = ref<
  Array<{ daily_slip_id: number; quiz_index: number; question: string; options: string[] }>
>([]);
const choices = ref<Record<number, number | null>>({});
const story = ref("");
const canvasRef = ref<HTMLCanvasElement | null>(null);
const cardTemplate = ref(0);
const shareLines = ref<string[]>([]);
const shareLoading = ref(false);
/** 答题反馈：仅用于答对时的勾选动效 */
const quizFeedback = ref<Record<number, { correct: boolean }>>({});
const shareCanvasPop = ref(false);

const templateLabels = ["边塞褐金", "青简翠墨", "朱印素笺", "烽烟暮色", "月白风清"];

async function load() {
  const { data } = await http.get("/daily-slip/today");
  slip.value = data.slip as Record<string, unknown>;
  funFact.value = (data.fun_fact as string) || null;
  quizzes.value = (data.quizzes as typeof quizzes.value) || [];
  const init: Record<number, number | null> = {};
  for (const q of quizzes.value) init[q.quiz_index] = null;
  choices.value = init;
  quizFeedback.value = {};
}

async function submitQuiz(q: { daily_slip_id: number; quiz_index: number }) {
  const c = choices.value[q.quiz_index];
  if (c === null || c === undefined) return;
  if (!auth.token) {
    ElMessage.warning("登录后答题可获简册积分");
    return;
  }
  const { data } = await http.post("/daily-slip/answer", {
    daily_slip_id: q.daily_slip_id,
    choice_index: c,
    quiz_index: q.quiz_index,
  });
  quizFeedback.value = { ...quizFeedback.value, [q.quiz_index]: { correct: !!data.correct } };
  ElMessage[data.correct ? "success" : "info"](data.correct ? "善！答得中肯。" : "再读释文，细细推敲。");
}

async function quickRead() {
  if (!slip.value?.transcription) return;
  const { data } = await http.post("/quick-read", {
    transcription: String(slip.value.transcription),
  });
  story.value = data.story;
}

function paletteForTemplate(t: number) {
  const palettes = [
    { bg0: "#3d2914", bg1: "#5c3d1e", bg2: "#8b5a2b", accent: "rgba(201, 176, 138, 0.35)", foot: "rgba(154, 52, 18, 0.65)" },
    { bg0: "#1a3d2e", bg1: "#2d5a45", bg2: "#4a7c59", accent: "rgba(180, 220, 200, 0.35)", foot: "rgba(34, 139, 34, 0.55)" },
    { bg0: "#3b2a2a", bg1: "#5c3a3a", bg2: "#8b4545", accent: "rgba(220, 180, 180, 0.35)", foot: "rgba(139, 0, 0, 0.5)" },
    { bg0: "#2a2438", bg1: "#3d3550", bg2: "#5a4a6e", accent: "rgba(200, 190, 230, 0.3)", foot: "rgba(147, 112, 219, 0.55)" },
    { bg0: "#e8e4dc", bg1: "#d4cfc4", bg2: "#c4bdb0", accent: "rgba(60, 50, 40, 0.2)", foot: "rgba(80, 70, 60, 0.55)" },
  ];
  return palettes[t % palettes.length];
}

function drawCard() {
  const c = canvasRef.value;
  if (!c || !slip.value) return;
  const ctx = c.getContext("2d");
  if (!ctx) return;
  c.width = 720;
  c.height = 400;
  const t = cardTemplate.value;
  const pal = paletteForTemplate(t);
  const grd = ctx.createLinearGradient(0, 0, 720, 400);
  grd.addColorStop(0, pal.bg0);
  grd.addColorStop(0.45, pal.bg1);
  grd.addColorStop(1, pal.bg2);
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, 720, 400);
  ctx.strokeStyle = pal.accent;
  ctx.lineWidth = 2;
  ctx.strokeRect(24, 24, 672, 352);
  const titleColor = t === 4 ? "#2c2416" : "#f6ecda";
  const subColor = t === 4 ? "#4a4035" : "rgba(246, 236, 218, 0.85)";
  ctx.fillStyle = titleColor;
  ctx.font = '600 30px "Noto Serif SC", "SimSun", serif';
  ctx.fillText("问牍·青声", 48, 72);
  ctx.fillStyle = subColor;
  ctx.font = '18px "Noto Serif SC", "SimSun", serif';
  ctx.fillText(String(slip.value.code || ""), 48, 118);
  const tit = String(slip.value.title || "");
  ctx.fillText(tit.slice(0, 20), 48, 158);
  ctx.font = '14px "Microsoft YaHei", sans-serif';
  const ver = String(slip.value.transcription || "").slice(0, 72);
  ctx.fillText(ver, 48, 200);
  ctx.fillStyle = pal.foot;
  ctx.font = '12px "Noto Serif SC", serif';
  ctx.fillText(`${templateLabels[t]} · 简册一叶`, 48, 360);
  ElMessage.success("牍卡已成，可右键保存画布");
  shareCanvasPop.value = true;
  window.setTimeout(() => {
    shareCanvasPop.value = false;
  }, 720);
}

async function loadShareCopy() {
  if (!slip.value) return;
  shareLoading.value = true;
  shareLines.value = [];
  try {
    const { data } = await http.post("/share-copy-suggestions", {
      title: String(slip.value.title || slip.value.code || "今日一牍"),
      snippet: `${String(slip.value.transcription || "").slice(0, 200)} ${String(slip.value.vernacular || "").slice(0, 200)}`,
    });
    shareLines.value = data.lines || [];
  } catch {
    shareLines.value = [];
  } finally {
    shareLoading.value = false;
  }
}

function copyTxt(label: string, text: string) {
  const t = text || "";
  if (!t) return;
  navigator.clipboard.writeText(t).then(
    () => ElMessage.success(`已复制${label}`),
    () => ElMessage.error("复制失败")
  );
}

onMounted(load);
</script>

<template>
  <div v-if="slip" class="page dj-page">
    <header class="daily-intro">
      <span class="dj-kicker daily-kicker">日课 · 每日一牍</span>
      <p class="daily-lead">一枚简牍、一段释读，配以小题巩固；持之以恒，自能辨体例、识名物。</p>
    </header>
    <el-card class="slip-board dj-slip-card">
      <div class="board-head">
        <h2 class="dj-heading board-h2">今日一牍 · {{ slip.code }}</h2>
        <p class="slip-title">{{ slip.title }}</p>
      </div>
      <div v-if="slipImageSrc(String(slip.image_url || ''))" class="daily-fig">
        <img
          :src="slipImageSrc(String(slip.image_url || ''))"
          :alt="`今日简牍影像 ${slip.code}`"
          class="daily-img"
          loading="lazy"
        />
      </div>
      <el-descriptions :column="1" border class="slip-desc">
        <el-descriptions-item label="释文">{{ slip.transcription }}</el-descriptions-item>
        <el-descriptions-item label="绎白">{{ slip.vernacular }}</el-descriptions-item>
        <el-descriptions-item label="出土地">{{ slip.site_name }}</el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-if="funFact"
        :title="'牍外一斑：' + funFact"
        type="success"
        :closable="false"
        class="fact-alert"
        show-icon
      />
      <div class="copy-row">
        <el-button size="small" @click="copyTxt('释文', String(slip.transcription || ''))">复制释文</el-button>
        <el-button size="small" @click="copyTxt('绎白', String(slip.vernacular || ''))">复制绎白</el-button>
      </div>

      <div v-for="q in quizzes" :key="q.quiz_index" class="quiz">
        <h4 class="dj-heading">日课 {{ quizzes.length > 1 ? `第 ${q.quiz_index + 1} 题` : "" }}</h4>
        <p class="qtext">{{ q.question }}</p>
        <el-radio-group v-model="choices[q.quiz_index]" class="quiz-rg">
          <el-radio
            v-for="(o, i) in q.options"
            :key="i"
            :label="i"
            class="block quiz-radio"
            :class="{
              'quiz-radio--correct':
                quizFeedback[q.quiz_index]?.correct && choices[q.quiz_index] === i,
            }"
          >
            {{ o }}
          </el-radio>
        </el-radio-group>
        <el-button type="primary" class="mt" @click="submitQuiz(q)">呈卷</el-button>
      </div>

      <div class="actions">
        <el-button @click="quickRead">三分钟快读（牍师绎为故事）</el-button>
      </div>
      <div class="card-tools">
        <span class="lbl">牍卡模板</span>
        <el-radio-group v-model="cardTemplate" size="small">
          <el-radio-button v-for="(lab, i) in templateLabels" :key="i" :label="i">{{ lab }}</el-radio-button>
        </el-radio-group>
        <el-button type="primary" plain @click="drawCard">生成牍卡（Canvas）</el-button>
        <el-button :loading="shareLoading" @click="loadShareCopy">生成分享语</el-button>
      </div>
      <div v-if="shareLines.length" class="share-lines">
        <p v-for="(line, i) in shareLines" :key="i" class="share-line">
          {{ line }}
          <el-button size="small" link type="primary" @click="copyTxt('文案', line)">复制</el-button>
        </p>
      </div>
      <p v-if="story" class="story">{{ story }}</p>

      <div :class="['canvas-wrap', { 'canvas-wrap--pop': shareCanvasPop }]">
        <canvas ref="canvasRef" class="canvas" />
      </div>
    </el-card>
  </div>
  <el-empty v-else description="牍册加载中，或尚未排定今日简牍" />
</template>

<style scoped>
.page {
  padding-bottom: 40px;
}
.daily-intro {
  margin-bottom: 14px;
}
.daily-kicker {
  margin-bottom: 8px;
}
.daily-lead {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--dj-ink-soft);
  max-width: 42em;
}
.board-h2 {
  font-size: 22px;
  letter-spacing: 0.05em;
}
.slip-board {
  padding-left: 4px;
}
.board-head {
  margin-bottom: 16px;
}
.board-head h2 {
  margin: 0 0 8px;
  font-size: 22px;
}
.slip-title {
  margin: 0;
  font-size: 16px;
  color: var(--dj-ink-soft);
  font-family: var(--dj-font-display);
}
.daily-fig {
  margin: 12px 0 16px;
  text-align: center;
}
.daily-img {
  max-width: 100%;
  max-height: min(55vh, 520px);
  object-fit: contain;
  border-radius: 6px;
  border: 1px solid var(--dj-border-light);
  background: #2a2218;
  box-shadow: 0 4px 14px var(--dj-shadow);
}
.slip-desc {
  margin-top: 8px;
}
.fact-alert {
  margin-top: 14px;
}
.copy-row {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.quiz {
  margin-top: 24px;
  padding: 18px 18px 16px;
  border-radius: var(--dj-radius-sm);
  border: 1px solid rgba(201, 176, 138, 0.38);
  background: linear-gradient(
    160deg,
    rgba(255, 252, 245, 0.95) 0%,
    rgba(239, 226, 204, 0.4) 100%
  );
  box-shadow: 0 2px 12px rgba(42, 34, 24, 0.04);
}
.qtext {
  line-height: 1.7;
  color: var(--dj-ink);
  margin: 0 0 12px;
}
.block {
  display: block;
  margin: 8px 0;
}
.quiz-rg {
  display: block;
  width: 100%;
}
.quiz-radio--correct :deep(.el-radio__label) {
  position: relative;
  padding-right: 26px;
}
.quiz-radio--correct :deep(.el-radio__label)::after {
  content: "";
  position: absolute;
  right: 0;
  top: 50%;
  width: 18px;
  height: 18px;
  margin-top: -9px;
  border-radius: 50%;
  border: 2px solid rgba(201, 162, 39, 0.95);
  background: radial-gradient(circle at 35% 30%, rgba(255, 236, 160, 0.95), rgba(201, 162, 39, 0.35));
  box-shadow: 0 0 12px rgba(255, 220, 120, 0.55);
  animation: dj-gold-tick 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes dj-gold-tick {
  0% {
    opacity: 0;
    transform: scale(0.5);
  }
  70% {
    opacity: 1;
    transform: scale(1.08);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}
.mt {
  margin-top: 12px;
}
.actions {
  margin-top: 20px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.card-tools {
  margin-top: 18px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.card-tools .lbl {
  font-size: 13px;
  color: var(--dj-ink-soft);
}
.share-lines {
  margin-top: 12px;
  padding: 12px 14px;
  background: rgba(255, 251, 243, 0.9);
  border-radius: 6px;
  border: 1px solid var(--dj-border-light);
}
.share-line {
  margin: 6px 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--dj-ink);
}
.story {
  margin-top: 16px;
  padding: 14px 16px;
  line-height: 1.85;
  color: var(--dj-ink);
  white-space: pre-wrap;
  background: rgba(255, 251, 243, 0.9);
  border-left: 3px solid var(--dj-seal);
  border-radius: 0 6px 6px 0;
}
.canvas-wrap {
  margin-top: 16px;
  display: inline-block;
  max-width: 100%;
  border-radius: 8px;
  transition: transform 0.45s ease, box-shadow 0.45s ease;
}
.canvas-wrap--pop {
  animation: dj-canvas-pop 0.72s cubic-bezier(0.22, 1, 0.36, 1) both;
  box-shadow: 0 12px 40px rgba(139, 90, 43, 0.18);
}
@keyframes dj-canvas-pop {
  0% {
    opacity: 0.85;
    transform: scale(0.92);
  }
  55% {
    opacity: 1;
    transform: scale(1.02);
  }
  100% {
    transform: scale(1);
  }
}
.canvas {
  display: block;
  max-width: 100%;
  border-radius: 6px;
  border: 1px solid var(--dj-border-light);
  box-shadow: 0 4px 16px var(--dj-shadow);
}

@media (prefers-reduced-motion: reduce) {
  .quiz-radio--correct :deep(.el-radio__label)::after {
    animation: none;
  }
  .canvas-wrap--pop {
    animation: none;
  }
}
</style>
