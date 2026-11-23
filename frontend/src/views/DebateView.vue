<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import http from "@/api/http";

const fallback = [
  { label: "简牍数字化是否应优先于原件整理发表", value: "简牍数字化是否应优先于原件整理发表" },
  { label: "边塞简牍能否单独支撑一部「大众史」", value: "边塞简牍能否单独支撑一部「大众史」" },
  { label: "AI 释读简牍是否会削弱传统文字学训练", value: "AI 释读简牍是否会削弱传统文字学训练" },
  { label: "公众考古热度是否会稀释简牍研究的严肃性", value: "公众考古热度是否会稀释简牍研究的严肃性" },
  { label: "简牍释文是否应在未定字处保留更多「存疑」", value: "简牍释文是否应在未定字处保留更多「存疑」而非强行隶定" },
  { label: "出土简牍能否作为中学历史教材的主干史料", value: "出土简牍能否作为中学历史教材的主干史料" },
  { label: "私人收藏简牍影像的流通边界应如何划定", value: "私人收藏简牍影像的流通边界应如何划定" },
  { label: "机器转写与人工隶定何者更应作为学术引用底本", value: "机器转写与人工隶定：何者更应作为学术引用的底本" },
  { label: "简牍数据库开放获取与文物信息安全如何平衡", value: "简牍数据库的「开放获取」与文物信息安全如何平衡" },
];

const topics = ref(fallback);
const topic = ref(fallback[0].value);
const side = ref<"正方" | "反方">("正方");
const argument = ref("");
const followUp = ref("");
const endNote = ref("");
const persona = ref<"master" | "clerk" | "soldier">("master");
const intensity = ref<"mild" | "standard" | "sharp">("standard");

const loading = ref(false);

type TurnCloseKind = "yield" | "conclude" | null;

type DebateTurn = {
  id: number;
  round: number;
  userText: string;
  thinking: string;
  rebuttal: string;
  closeKind: TurnCloseKind;
  at: number;
};

const turns = ref<DebateTurn[]>([]);
/** 已认输或鸣金，不可再续论 */
const sessionEnded = ref(false);

const MAX_ROUNDS = 12;

const argLen = computed(() => argument.value.replace(/\s/g, "").length);
const followLen = computed(() => followUp.value.replace(/\s/g, "").length);

const sessionLive = computed(() => turns.value.length > 0 && !sessionEnded.value);
const canContinue = computed(() => sessionLive.value && turns.value.length < MAX_ROUNDS);

const personaLabel: Record<string, string> = {
  master: "牍师（通识）",
  clerk: "刀笔吏（文书律令）",
  soldier: "戍卒（边塞实务）",
};

const intensityLabel: Record<string, string> = {
  mild: "温厚",
  standard: "平实",
  sharp: "峻切",
};

function priorPayload() {
  return turns.value.map((t) => ({
    user: t.userText,
    rebuttal: t.rebuttal,
  }));
}

async function copyText(text: string) {
  const t = text.trim();
  if (!t) return;
  try {
    await navigator.clipboard.writeText(t);
    ElMessage.success("已复制到剪贴板");
  } catch {
    ElMessage.error("复制失败，请手动选择文本");
  }
}

function resetSession() {
  turns.value = [];
  sessionEnded.value = false;
  followUp.value = "";
  endNote.value = "";
  argument.value = "";
}

async function submitOpen() {
  if (!argument.value.trim()) {
    ElMessage.warning("请先写下首轮立论");
    return;
  }
  loading.value = true;
  try {
    const { data } = await http.post("/debate", {
      phase: "open",
      topic: topic.value,
      side: side.value,
      argument: argument.value.trim(),
      persona: persona.value,
      intensity: intensity.value,
    });
    const th = String(data.thinking || "").trim();
    const rb = String(data.rebuttal || "").trim();
    turns.value = [
      {
        id: Date.now(),
        round: 1,
        userText: argument.value.trim(),
        thinking: th,
        rebuttal: rb,
        closeKind: null,
        at: Date.now(),
      },
    ];
  } catch {
    ElMessage.error("辩难未达，请检查网络后重试");
  } finally {
    loading.value = false;
  }
}

async function submitContinue() {
  if (!followUp.value.trim()) {
    ElMessage.warning("请写下本轮续论或对驳辞的回应");
    return;
  }
  loading.value = true;
  try {
    const { data } = await http.post("/debate", {
      phase: "continue",
      topic: topic.value,
      side: side.value,
      argument: followUp.value.trim(),
      persona: persona.value,
      intensity: intensity.value,
      prior_turns: priorPayload(),
    });
    const th = String(data.thinking || "").trim();
    const rb = String(data.rebuttal || "").trim();
    const nextRound = turns.value.length + 1;
    turns.value = [
      ...turns.value,
      {
        id: Date.now(),
        round: nextRound,
        userText: followUp.value.trim(),
        thinking: th,
        rebuttal: rb,
        closeKind: null,
        at: Date.now(),
      },
    ];
    followUp.value = "";
  } catch {
    ElMessage.error("辩难未达，请检查网络后重试");
  } finally {
    loading.value = false;
  }
}

async function submitYield() {
  try {
    await ElMessageBox.confirm(
      "认输即认对方本轮论证占优，牍师将以礼收束，不作讥讽。确认认输？",
      "认输（甘拜下风）",
      { type: "warning", confirmButtonText: "确认认输", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }
  loading.value = true;
  try {
    const { data } = await http.post("/debate", {
      phase: "yield",
      topic: topic.value,
      side: side.value,
      argument: endNote.value.trim(),
      persona: persona.value,
      intensity: intensity.value,
      prior_turns: priorPayload(),
    });
    const th = String(data.thinking || "").trim();
    const rb = String(data.rebuttal || "").trim();
    const note = endNote.value.trim();
    turns.value = [
      ...turns.value,
      {
        id: Date.now(),
        round: turns.value.length + 1,
        userText: note ? `【认输】${note}` : "【认输】",
        thinking: th,
        rebuttal: rb,
        closeKind: "yield",
        at: Date.now(),
      },
    ];
    sessionEnded.value = true;
    endNote.value = "";
    ElMessage.success("本场已认输收束");
  } catch {
    ElMessage.error("未能完成收束，请稍后重试");
  } finally {
    loading.value = false;
  }
}

async function submitConclude() {
  try {
    await ElMessageBox.confirm(
      "鸣金收兵即友好结束辩论，牍师将作小结与陈谢，不分胜负。确认结束？",
      "鸣金收兵",
      { confirmButtonText: "确认收兵", cancelButtonText: "再想想" }
    );
  } catch {
    return;
  }
  loading.value = true;
  try {
    const { data } = await http.post("/debate", {
      phase: "conclude",
      topic: topic.value,
      side: side.value,
      argument: endNote.value.trim(),
      persona: persona.value,
      intensity: intensity.value,
      prior_turns: priorPayload(),
    });
    const th = String(data.thinking || "").trim();
    const rb = String(data.rebuttal || "").trim();
    const note = endNote.value.trim();
    turns.value = [
      ...turns.value,
      {
        id: Date.now(),
        round: turns.value.length + 1,
        userText: note ? `【鸣金】${note}` : "【鸣金】",
        thinking: th,
        rebuttal: rb,
        closeKind: "conclude",
        at: Date.now(),
      },
    ];
    sessionEnded.value = true;
    endNote.value = "";
    ElMessage.success("本场已鸣金收束");
  } catch {
    ElMessage.error("未能完成收束，请稍后重试");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const { data } = await http.get("/public/debate-topics");
    const items: string[] = data.items || [];
    if (items.length) {
      topics.value = items.map((t) => ({ label: t.length > 42 ? `${t.slice(0, 40)}…` : t, value: t }));
      topic.value = topics.value[0].value;
    }
  } catch {
    /* 使用本地 fallback */
  }
});
</script>

<template>
  <div class="page dj-page debate-page">
    <span class="dj-kicker">思辨雅席</span>
    <h1 class="dj-heading debate-h1">辩论社</h1>
    <p class="intro">
      首轮<strong>立论</strong>后，可据牍师驳辞多轮<strong>续论</strong>；亦可按古礼<strong>认输收束</strong>或<strong>鸣金收兵</strong>（和局式友好结束）。辩题、持方与人设首轮后锁定至「新开一场」。生成内容仅供学习讨论。
    </p>

    <el-card class="dj-slip-card form-card">
      <template #header>
        <span>立论与场务</span>
        <span class="header-hint">
          <template v-if="!turns.length">首轮请完整立论；交锋开始后可续论或收束。</template>
          <template v-else-if="sessionEnded">本场已结束，可「新开一场」。</template>
          <template v-else>第 {{ turns.length }} 轮已毕，可续论或收束（至多 {{ MAX_ROUNDS }} 轮交锋）。</template>
        </span>
      </template>
      <el-form label-position="top" aria-label="辩论表单">
        <el-form-item label="辩题">
          <el-select
            v-model="topic"
            filterable
            allow-create
            default-first-option
            class="topic-select"
            :disabled="sessionLive || sessionEnded"
            aria-label="选择或输入辩题"
          >
            <el-option v-for="t in topics" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="你所持方">
          <el-radio-group v-model="side" :disabled="sessionLive || sessionEnded">
            <el-radio-button label="正方" />
            <el-radio-button label="反方" />
          </el-radio-group>
        </el-form-item>
        <el-form-item label="辩席人设">
          <el-radio-group v-model="persona" class="persona-group" :disabled="sessionLive || sessionEnded">
            <el-radio-button label="master">牍师</el-radio-button>
            <el-radio-button label="clerk">刀笔吏</el-radio-button>
            <el-radio-button label="soldier">戍卒</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="驳难力度">
          <el-segmented
            v-model="intensity"
            :disabled="sessionLive || sessionEnded"
            :options="[
              { label: '温厚', value: 'mild' },
              { label: '平实', value: 'standard' },
              { label: '峻切', value: 'sharp' },
            ]"
          />
        </el-form-item>
        <el-form-item>
          <template #label>
            <span>首轮立论</span>
            <span class="label-meta">建议 80～300 字 · 已 {{ argLen }} 字（不计空白）</span>
          </template>
          <el-input
            v-model="argument"
            type="textarea"
            :rows="6"
            maxlength="1200"
            show-word-limit
            :disabled="!!turns.length"
            placeholder="宜交代前提、关键概念与推理或例证。首轮提交后不可再改，请谨慎。"
          />
        </el-form-item>

        <template v-if="sessionLive">
          <el-divider content-position="left">续论</el-divider>
          <el-form-item>
            <template #label>
              <span>对驳辞的回应（续论）</span>
              <span class="label-meta">已 {{ followLen }} 字</span>
            </template>
            <el-input
              v-model="followUp"
              type="textarea"
              :rows="5"
              maxlength="1200"
              show-word-limit
              placeholder="可逐条回应对方驳辞，或补充史料、修正定义；避免空泛重复首轮。"
            />
          </el-form-item>
          <el-form-item label="认输 / 鸣金时可附一言（选填）">
            <el-input v-model="endNote" maxlength="200" show-word-limit placeholder="例：某处论证确有不周，愿闻后绪。" />
          </el-form-item>
        </template>

        <el-collapse v-if="!turns.length" class="tips-collapse">
          <el-collapse-item title="立论小引（可点开参考）" name="1">
            <ul class="tips-list">
              <li>先界定辩题中的核心词在你方的操作定义。</li>
              <li>区分「事实判断」与「价值判断」。</li>
              <li>多轮时：后续请直指对方上一段驳辞中的具体论断。</li>
            </ul>
          </el-collapse-item>
        </el-collapse>

        <div class="form-actions">
          <el-button v-if="!turns.length" type="primary" :loading="loading" @click="submitOpen">请对方驳难（首轮）</el-button>
          <template v-else-if="!sessionEnded">
            <el-button type="primary" :loading="loading" :disabled="!canContinue" @click="submitContinue">
              继续请驳（第 {{ turns.length + 1 }} 轮）
            </el-button>
            <el-button type="warning" plain :loading="loading" @click="submitYield">认输</el-button>
            <el-button :loading="loading" @click="submitConclude">鸣金收兵</el-button>
          </template>
          <el-button v-if="turns.length" @click="resetSession">新开一场</el-button>
        </div>
        <p v-if="sessionLive && !canContinue" class="round-cap">已达交锋轮次上限，请认输或鸣金收束本场。</p>
      </el-form>
    </el-card>

    <div v-if="loading && !turns.length" class="mt loading-block">
      <el-skeleton animated :rows="5" />
      <p class="loading-tip">牍师斟酌立论与辩题……</p>
    </div>

    <el-card
      v-if="turns.length"
      v-loading="loading"
      class="mt dj-slip-card transcript-card"
      element-loading-text="牍师斟酌中……"
    >
      <template #header>
        <div class="outcome-head">
          <span>辩场实录</span>
          <div class="outcome-meta">
            <el-tag size="small" type="info">{{ personaLabel[persona] }}</el-tag>
            <el-tag size="small">{{ intensityLabel[intensity] }}</el-tag>
            <el-tag size="small" effect="plain">{{ side }}</el-tag>
            <el-tag v-if="sessionEnded" size="small" type="success">已收束</el-tag>
          </div>
        </div>
      </template>

      <div v-for="t in turns" :key="t.id" class="turn-block">
        <div class="turn-head">
          <span class="turn-label">第 {{ t.round }} 轮</span>
          <span v-if="t.closeKind === 'yield'" class="turn-tag yield">认输收束</span>
          <span v-else-if="t.closeKind === 'conclude'" class="turn-tag conclude">鸣金收束</span>
          <span class="turn-time">{{ new Date(t.at).toLocaleString() }}</span>
        </div>
        <div class="user-utter">
          <span class="utter-kicker">持方</span>
          <p class="utter-body">{{ t.userText }}</p>
        </div>
        <div v-if="t.thinking" class="thinking-wrap">
          <p class="thinking-kicker">牍师沉吟</p>
          <div class="thinking-bubble" role="status">
            <p class="thinking-text">{{ t.thinking }}</p>
          </div>
          <el-button size="small" text type="primary" class="copy-btn" @click="copyText(t.thinking)">复制沉吟</el-button>
        </div>
        <div class="rebut-block">
          <div class="rebut-head">
            <span class="rebut-title">{{ t.closeKind ? "牍师收束" : "牍师驳辞" }}</span>
            <el-button size="small" plain @click="copyText(t.rebuttal)">复制本段</el-button>
          </div>
          <p class="rebut-text">{{ t.rebuttal }}</p>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.debate-page {
  padding-bottom: 40px;
}
.debate-h1 {
  font-size: 22px;
  margin: 0 0 12px;
  letter-spacing: 0.06em;
}
.intro {
  margin: 0 0 18px;
  max-width: 48em;
  line-height: 1.75;
  color: var(--dj-ink-soft);
  font-size: 14px;
}
.intro strong {
  font-weight: 600;
  color: var(--dj-ink, #3d3028);
}
.form-card :deep(.el-card__header) {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
}
.header-hint {
  font-size: 12px;
  font-weight: normal;
  color: var(--dj-ink-soft);
  letter-spacing: 0.02em;
}
.topic-select {
  width: 100%;
}
.persona-group {
  flex-wrap: wrap;
}
.label-meta {
  margin-left: 8px;
  font-size: 12px;
  font-weight: normal;
  color: var(--dj-ink-soft);
}
.tips-collapse {
  margin-bottom: 14px;
  border: none;
  --el-collapse-header-bg-color: transparent;
}
.tips-collapse :deep(.el-collapse-item__header) {
  font-size: 13px;
  color: var(--dj-bamboo, #6b5344);
}
.tips-list {
  margin: 0;
  padding-left: 1.2em;
  font-size: 13px;
  line-height: 1.65;
  color: var(--dj-ink-soft);
}
.form-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.round-cap {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--dj-ink-soft);
}
.mt {
  margin-top: 16px;
}
.loading-block {
  padding: 8px 0;
}
.loading-tip {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--dj-ink-soft);
}
.transcript-card {
  border-left: 3px solid var(--dj-seal);
}
.outcome-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
}
.outcome-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.turn-block {
  padding: 16px 0;
  border-bottom: 1px dashed rgba(110, 88, 58, 0.14);
}
.turn-block:last-child {
  border-bottom: none;
  padding-bottom: 4px;
}
.turn-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 12px;
}
.turn-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--dj-ink);
  letter-spacing: 0.08em;
}
.turn-time {
  font-size: 12px;
  color: var(--dj-ink-soft);
}
.turn-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  letter-spacing: 0.06em;
}
.turn-tag.yield {
  color: #8b5a2b;
  background: rgba(180, 100, 40, 0.12);
}
.turn-tag.conclude {
  color: #3d6a5a;
  background: rgba(60, 120, 100, 0.12);
}
.user-utter {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(154, 72, 38, 0.06);
  border: 1px solid rgba(154, 90, 48, 0.1);
}
.utter-kicker {
  display: block;
  font-size: 10px;
  letter-spacing: 0.28em;
  color: var(--dj-bamboo);
  margin-bottom: 6px;
}
.utter-body {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--dj-ink);
  white-space: pre-wrap;
}
.thinking-wrap {
  margin-bottom: 14px;
}
.thinking-kicker {
  margin: 0 0 8px;
  font-size: 11px;
  letter-spacing: 0.28em;
  color: var(--dj-ink-soft);
}
.thinking-bubble {
  position: relative;
  max-width: min(400px, 100%);
  padding: 12px 16px 14px;
  border-radius: 14px;
  background: linear-gradient(165deg, rgba(248, 250, 255, 0.98) 0%, rgba(232, 236, 248, 0.94) 100%);
  border: 1px solid rgba(90, 107, 138, 0.22);
  box-shadow:
    0 2px 0 rgba(255, 255, 255, 0.85) inset,
    0 6px 18px rgba(48, 32, 18, 0.06);
}
.thinking-bubble::after {
  content: "";
  position: absolute;
  left: 24px;
  bottom: -7px;
  width: 0;
  height: 0;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-top: 8px solid rgba(232, 236, 248, 0.94);
  filter: drop-shadow(0 1px 0 rgba(90, 107, 138, 0.1));
}
.thinking-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  letter-spacing: 0.03em;
  color: var(--dj-ink, #3d3228);
}
.copy-btn {
  margin-top: 8px;
}
.rebut-block {
  padding-top: 4px;
}
.rebut-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.rebut-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--dj-ink);
  letter-spacing: 0.08em;
}
.rebut-text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.85;
  font-size: 15px;
  color: var(--dj-ink);
}
</style>
