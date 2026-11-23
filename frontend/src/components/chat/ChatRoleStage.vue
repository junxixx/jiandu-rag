<script setup lang="ts">
import { computed, ref, watch } from "vue";
import ChatAvatar3D from "./ChatAvatar3D.vue";
import ChatPortraitImg from "./ChatPortraitImg.vue";

export type StageRole = {
  role_key: string;
  label: string;
  card_title: string;
  hint: string;
};

const props = withDefaults(
  defineProps<{
    rolesCatalog: StageRole[];
    /** 单聊主角色 */
    primaryRoleKey: string;
    isGroup: boolean;
    groupRoleKeys: string[];
    show3d: boolean;
    /** 与对话联动：idle / thinking / speaking */
    avatarPose?: "idle" | "thinking" | "speaking";
  }>(),
  {
    avatarPose: "idle",
  }
);

const ACCENTS: Record<string, string> = {
  li_gan: "#8b6914",
  shang_guan: "#5a6b7c",
  ban_chao: "#7a4a28",
  geng_gong: "#4a6a7a",
  zhang_qian: "#9a7b3a",
  fu_jiezi: "#8b5040",
};

function metaFor(key: string): StageRole | undefined {
  return props.rolesCatalog.find((r) => r.role_key === key);
}

const primaryAccent = computed(
  () => ACCENTS[props.primaryRoleKey] || "#8b6914"
);

const groupMetas = computed(() =>
  props.groupRoleKeys.map((k) => ({ key: k, meta: metaFor(k), accent: ACCENTS[k] || "#6b5a4a" }))
);

const poseLabel = computed(() => {
  if (!props.show3d) return "";
  const p = props.avatarPose;
  if (p === "thinking") return "凝思候答";
  if (p === "speaking") return "对谈陈辞";
  return "戍影待机";
});

const poseLabelGroup = computed(() => {
  if (!props.show3d) return "";
  const p = props.avatarPose;
  if (p === "thinking") return "同席候答";
  if (p === "speaking") return "依次陈辞";
  return "同席侍立";
});

/** 思考态语气（可按 role_key 扩展，并与 default 合并后随机） */
const BUBBLE_THINKING: Record<string, readonly string[]> = {
  li_gan: ["指尖轻叩简侧……", "烽上旧事，一一掠过心头。", "候长若在此，会怎生下笔？"],
  shang_guan: ["律令条文，须逐字核对。", "此式是否合牒？", "且容某斟酌体式。"],
  ban_chao: ["西域道里，又在胸中过了一遍。", "吏士粮水，不可不慎。", "汉廷与诸国之间，分寸要紧。"],
  geng_gong: ["城上风紧……先稳住心神。", "粮水可数，士气不可泄。", "再思一遍攻守之序。"],
  zhang_qian: ["大漠沙碛，如在目前。", "凿空之路，险处历历在目。", "使节之礼，不可轻忽。"],
  fu_jiezi: ["西域局势，须臾万变。", "一言既出，干系非小。", "且思汉廷方略如何措辞。"],
  default: ["凝神细想……", "沉吟未已……", "容某斟酌片刻。", "此事还须再想一层。"],
};

/** 答问态语气 */
const BUBBLE_SPEAKING: Record<string, readonly string[]> = {
  li_gan: ["某这便禀来——", "边塞所见，如实道来。", "照烽上规矩，这般说与你听。"],
  shang_guan: ["依律令与体式，如此书之。", "牒上该当这样写。", "刀笔所录，大意如下。"],
  ban_chao: ["某以所见所闻，略陈一二。", "定远所历，可从此说起。", "西域事体，且听某道来。"],
  geng_gong: ["守城之日，实情如此。", "疏勒城下，某亲历者……", "边事艰危，不敢虚美。"],
  zhang_qian: ["奉使所见，约略如此。", "凿空途中，曾遇……", "汉与西域往来，大意若此。"],
  fu_jiezi: ["西域事功，某所知者……", "一言以蔽之……", "当时情势，说来话长，先答你这问。"],
  default: ["且听某慢慢道来。", "这般说与你听。", "某试陈所见。", "容某逐条答来。"],
};

function pickRandomLine(lines: string[]): string {
  if (!lines.length) return "";
  return lines[Math.floor(Math.random() * lines.length)] ?? "";
}

function bubbleLinesFor(pose: "thinking" | "speaking", roleKey: string): string[] {
  const table = pose === "thinking" ? BUBBLE_THINKING : BUBBLE_SPEAKING;
  const own = table[roleKey] ?? [];
  const fallback = table.default ?? [];
  return [...own, ...fallback];
}

/** 群席：合并同席各人语气池，并混入几句「同席」口吻 */
function bubbleLinesForGroup(pose: "thinking" | "speaking"): string[] {
  const keys = props.groupRoleKeys.filter(Boolean);
  const merged: string[] = [];
  for (const k of keys) {
    merged.push(...bubbleLinesFor(pose, k));
  }
  const extra =
    pose === "thinking"
      ? [
          "同席诸君，共候尺牍之答……",
          "此问牵涉多方，容某等细想。",
          "诸席静默，且听问端落点。",
          "各怀所见，且斟酌如何分答。",
        ]
      : [
          "且听同席各陈首尾……",
          "诸君依次道来便是。",
          "某等这一轮，各答所司。",
          "同席数语，互为补苴。",
        ];
  return [...merged, ...extra];
}

const moodBubbleText = ref("");

watch(
  () =>
    [props.avatarPose, props.primaryRoleKey, props.show3d, props.isGroup, props.groupRoleKeys.join(",")] as const,
  ([pose, roleKey, show3d, isGroup]) => {
    if (pose === "idle") {
      moodBubbleText.value = "";
      return;
    }
    if (pose !== "thinking" && pose !== "speaking") {
      return;
    }
    if (!isGroup && !show3d) {
      moodBubbleText.value = "";
      return;
    }
    if (isGroup) {
      if (!props.groupRoleKeys.length) {
        moodBubbleText.value = "";
        return;
      }
      moodBubbleText.value = pickRandomLine(bubbleLinesForGroup(pose));
    } else {
      moodBubbleText.value = pickRandomLine(bubbleLinesFor(pose, roleKey));
    }
  },
  { immediate: true }
);

const moodBubbleVisible = computed(() => {
  const t = moodBubbleText.value;
  const pose = props.avatarPose;
  const activePose = pose === "thinking" || pose === "speaking";
  if (!activePose || t.length === 0) return false;
  if (props.isGroup) return true;
  return props.show3d;
});
</script>

<template>
  <div class="stage stage-premium">
    <div v-if="!isGroup" class="single">
      <div class="portrait-block">
        <div v-if="show3d" class="portrait-3d-column">
          <Transition name="mood-bubble">
            <div
              v-if="moodBubbleVisible"
              class="mood-bubble"
              :data-pose="avatarPose"
              role="status"
              aria-live="polite"
            >
              <p class="mood-bubble-inner">{{ moodBubbleText }}</p>
            </div>
          </Transition>
          <div class="portrait-3d-frame">
            <div class="portrait-3d-slot" :class="{ 'slot-li-gan': primaryRoleKey === 'li_gan' }">
              <ChatAvatar3D
                :role-key="primaryRoleKey"
                :accent="primaryAccent"
                :enabled="true"
                :avatar-pose="avatarPose"
                fill-container
              />
            </div>
          </div>
          <div class="pose-strip" :data-pose="avatarPose">
            <span class="pose-dot" aria-hidden="true" />
            <span class="pose-text">{{ poseLabel }}</span>
          </div>
        </div>
        <ChatPortraitImg
          v-else
          :role-key="primaryRoleKey"
          class="portrait"
          width="160"
          height="208"
          :alt="metaFor(primaryRoleKey)?.card_title || '夜话角色'"
        />
        <div class="name-block">
          <p class="role-kicker">本席夜话</p>
          <h2 class="role-title dj-heading">{{ metaFor(primaryRoleKey)?.card_title || "边塞夜话" }}</h2>
          <p class="role-sub">{{ metaFor(primaryRoleKey)?.label }}</p>
          <p v-if="metaFor(primaryRoleKey)?.hint" class="role-hint">{{ metaFor(primaryRoleKey)?.hint }}</p>
        </div>
      </div>
    </div>

    <div v-else class="group">
      <p class="group-lead">群儒夜话 · 本席出场</p>
      <div class="group-bubble-column">
        <Transition name="mood-bubble">
          <div
            v-if="moodBubbleVisible"
            class="mood-bubble group-mood-bubble"
            :data-pose="avatarPose"
            role="status"
            aria-live="polite"
          >
            <p class="mood-bubble-inner">{{ moodBubbleText }}</p>
          </div>
        </Transition>
      </div>
      <div class="group-row">
        <div v-for="g in groupMetas" :key="g.key" class="group-card">
          <div v-if="show3d" class="group-3d-frame">
            <div class="group-3d-slot" :class="{ 'slot-li-gan': g.key === 'li_gan' }">
              <ChatAvatar3D
                :role-key="g.key"
                :accent="g.accent"
                :enabled="true"
                :avatar-pose="avatarPose"
                fill-container
              />
            </div>
          </div>
          <ChatPortraitImg
            v-else
            :role-key="g.key"
            class="portrait-sm"
            width="72"
            height="94"
            :alt="g.meta?.card_title || g.key"
          />
          <span class="g-name">{{ g.meta?.label || g.key }}</span>
        </div>
      </div>
      <div v-if="show3d" class="pose-strip group-pose-strip" :data-pose="avatarPose">
        <span class="pose-dot" aria-hidden="true" />
        <span class="pose-text">{{ poseLabelGroup }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stage-premium {
  margin-bottom: 16px;
  padding: 18px 20px 20px;
  background: linear-gradient(145deg, rgba(255, 252, 246, 0.97) 0%, rgba(248, 238, 222, 0.88) 48%, rgba(240, 228, 208, 0.75) 100%);
  border: 1px solid rgba(110, 88, 58, 0.14);
  border-radius: 14px;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.75) inset,
    0 8px 28px rgba(58, 40, 22, 0.06);
}
.single {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: stretch;
}
.portrait-block {
  display: flex;
  gap: 18px;
  align-items: flex-start;
  flex: 1 1 240px;
  min-width: 0;
}
.portrait-3d-column {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.mood-bubble {
  position: relative;
  z-index: 2;
  max-width: min(240px, 92vw);
  margin-bottom: 2px;
  padding: 10px 14px 12px;
  border-radius: 14px;
  background: linear-gradient(165deg, rgba(255, 252, 248, 0.98) 0%, rgba(248, 238, 224, 0.96) 100%);
  border: 1px solid rgba(110, 88, 58, 0.18);
  box-shadow:
    0 2px 0 rgba(255, 255, 255, 0.85) inset,
    0 6px 18px rgba(48, 32, 18, 0.1);
}
.mood-bubble[data-pose="thinking"] {
  border-color: rgba(90, 107, 138, 0.22);
  background: linear-gradient(165deg, rgba(248, 250, 255, 0.98) 0%, rgba(232, 236, 248, 0.94) 100%);
}
.mood-bubble[data-pose="speaking"] {
  border-color: rgba(154, 100, 48, 0.22);
  background: linear-gradient(165deg, rgba(255, 250, 242, 0.99) 0%, rgba(252, 236, 216, 0.95) 100%);
}
.mood-bubble::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: -7px;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-top: 8px solid rgba(248, 238, 224, 0.96);
  filter: drop-shadow(0 1px 0 rgba(110, 88, 58, 0.12));
}
.mood-bubble[data-pose="thinking"]::after {
  border-top-color: rgba(232, 236, 248, 0.94);
}
.mood-bubble[data-pose="speaking"]::after {
  border-top-color: rgba(252, 236, 216, 0.95);
}
.mood-bubble-inner {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  letter-spacing: 0.04em;
  color: var(--dj-ink, #3d3228);
  text-align: center;
}
.mood-bubble-enter-active,
.mood-bubble-leave-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s ease;
}
.mood-bubble-enter-from,
.mood-bubble-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.96);
}
.portrait-3d-frame {
  padding: 3px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(180, 150, 100, 0.35) 0%, rgba(120, 90, 55, 0.2) 50%, rgba(200, 170, 120, 0.3) 100%);
  box-shadow: 0 4px 18px rgba(48, 32, 18, 0.08);
}
.portrait-3d-slot {
  width: 168px;
  height: 228px;
  min-height: 180px;
  border-radius: 11px;
  overflow: hidden;
  background: radial-gradient(ellipse 70% 60% at 50% 40%, #2a2218 0%, #1a1510 100%);
}
.portrait-3d-slot.slot-li-gan {
  width: 176px;
  height: 256px;
  min-height: 200px;
}
.portrait-3d-slot :deep(.avatar-3d-shell) {
  width: 100%;
  height: 100%;
  border-radius: 11px;
}
.portrait-3d-slot :deep(.avatar-3d-wrap) {
  box-sizing: border-box;
  border: none;
  box-shadow: none;
  border-radius: 11px;
}
.pose-strip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--dj-ink-soft, #5c4a3a);
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(110, 88, 58, 0.12);
  transition:
    color 0.35s ease,
    border-color 0.35s ease,
    background 0.35s ease;
}
.pose-strip[data-pose="thinking"] {
  color: #5a6b8a;
  border-color: rgba(90, 107, 138, 0.25);
  background: rgba(240, 244, 252, 0.75);
}
.pose-strip[data-pose="speaking"] {
  color: #7a4a28;
  border-color: rgba(154, 90, 40, 0.28);
  background: rgba(255, 246, 236, 0.85);
}
.pose-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--dj-bamboo, #8b7355);
  opacity: 0.85;
}
.pose-strip[data-pose="thinking"] .pose-dot {
  background: #6a7a9a;
  animation: pose-breathe 1.4s ease-in-out infinite;
}
.pose-strip[data-pose="speaking"] .pose-dot {
  background: #b87333;
  animation: pose-breathe 0.85s ease-in-out infinite;
}
@keyframes pose-breathe {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.65;
  }
  50% {
    transform: scale(1.25);
    opacity: 1;
  }
}
.pose-text {
  white-space: nowrap;
}
.portrait {
  flex-shrink: 0;
  width: 140px;
  height: auto;
  max-height: 182px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid var(--dj-border-light, #dccbb5);
  box-shadow: 0 2px 8px rgba(60, 40, 20, 0.08);
}
.name-block {
  min-width: 0;
  padding-left: 4px;
  border-left: 3px solid rgba(139, 105, 20, 0.2);
}
.role-kicker {
  margin: 0 0 6px;
  font-size: 10px;
  letter-spacing: 0.35em;
  text-transform: uppercase;
  color: var(--dj-ink-soft, #7a6a58);
  opacity: 0.9;
}
.role-title {
  font-size: 20px;
  margin: 0 0 6px;
  letter-spacing: 0.08em;
  font-weight: 600;
}
.role-sub {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--dj-bamboo, #6b5344);
}
.role-hint {
  margin: 0;
  font-size: 13px;
  color: var(--dj-ink-soft, #5c4a3a);
  line-height: 1.6;
}
.group {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}
.group-lead {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--dj-ink-soft);
  letter-spacing: 0.06em;
}
.group-bubble-column {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  min-height: 0;
}
.group-mood-bubble {
  max-width: min(320px, 94vw);
}
.group-pose-strip {
  margin-top: 12px;
  align-self: center;
}
.group-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.group-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255, 252, 246, 0.65);
  border: 1px solid rgba(110, 88, 58, 0.1);
  box-shadow: 0 2px 8px rgba(48, 32, 18, 0.04);
}
.group-3d-frame {
  padding: 2px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(180, 150, 100, 0.32) 0%, rgba(120, 90, 55, 0.18) 50%, rgba(200, 170, 120, 0.28) 100%);
  box-shadow: 0 3px 12px rgba(48, 32, 18, 0.06);
}
.group-3d-slot {
  width: 104px;
  height: 138px;
  border-radius: 8px;
  overflow: hidden;
  background: radial-gradient(ellipse 70% 60% at 50% 40%, #2a2218 0%, #1a1510 100%);
}
.group-3d-slot.slot-li-gan {
  width: 108px;
  height: 148px;
}
.group-3d-slot :deep(.avatar-3d-shell) {
  width: 100%;
  height: 100%;
  border-radius: 8px;
}
.group-3d-slot :deep(.avatar-3d-wrap) {
  box-sizing: border-box;
  border: none;
  box-shadow: none;
  border-radius: 8px;
}
.portrait-sm {
  border-radius: 6px;
  border: 1px solid var(--dj-border-light);
}
.g-name {
  font-size: 12px;
  color: var(--dj-ink);
  text-align: center;
  max-width: 104px;
}
</style>
