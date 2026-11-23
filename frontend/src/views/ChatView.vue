<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import ChatRoleStage from "@/components/chat/ChatRoleStage.vue";
import ChatPortraitImg from "@/components/chat/ChatPortraitImg.vue";

type SessionRow = {
  id: number;
  title: string;
  role_key: string;
  chat_mode?: string;
  group_roles?: string[] | null;
};

type RoleItem = {
  role_key: string;
  label: string;
  card_title: string;
  hint: string;
};

const sessions = ref<SessionRow[]>([]);
const activeId = ref<number | null>(null);
const messages = ref<Array<{ role: string; content: string }>>([]);
const input = ref("");
const sending = ref(false);
const roles = ref<RoleItem[]>([]);
const show3d = ref(true);
/** 群儒夜话：客户端自选 2～3 人（与 POST role_keys 一致） */
const groupRoleSelection = ref<string[]>([]);

/** 单聊三维小影：与对话节奏联动（思考 → 答问 → 待机） */
const avatarPose = ref<"idle" | "thinking" | "speaking">("idle");
let poseIdleTimer: ReturnType<typeof setTimeout> | null = null;

function clearPoseTimer() {
  if (poseIdleTimer) {
    clearTimeout(poseIdleTimer);
    poseIdleTimer = null;
  }
}

function scheduleReturnToIdle(afterMs: number) {
  clearPoseTimer();
  poseIdleTimer = setTimeout(() => {
    avatarPose.value = "idle";
    poseIdleTimer = null;
  }, afterMs);
}

const labelByKey = computed(() => {
  const m: Record<string, string> = {};
  for (const r of roles.value) {
    m[r.role_key] = r.label;
  }
  return m;
});

const activeSession = computed(() => sessions.value.find((s) => s.id === activeId.value) || null);

const stagePrimaryKey = computed(() => activeSession.value?.role_key || "li_gan");

const stageIsGroup = computed(() => (activeSession.value?.chat_mode || "single") === "group");

const stageGroupKeys = computed(() => {
  const g = activeSession.value?.group_roles;
  return Array.isArray(g) && g.length ? g : ["li_gan", "shang_guan"];
});

const poseHint = computed(() => {
  if (!show3d.value) return "";
  const p = avatarPose.value;
  if (p === "thinking") return "烽影凝思，候尺牍之答";
  if (p === "speaking") return "烽影陈辞，与问对相和";
  return "烽影待机，候君下一问";
});

const stagePoseHint = computed(() => {
  if (!show3d.value) return "";
  if (!stageIsGroup.value) return poseHint.value;
  const p = avatarPose.value;
  if (p === "thinking") return "群席烽影候答，诸席同屏";
  if (p === "speaking") return "群席陈辞相继，烽影与共";
  return "群席烽影并列，候君下一问";
});

function ensureDefaultGroupSelection() {
  const list = roles.value;
  if (!list.length) return;
  const valid = groupRoleSelection.value.filter((k) => list.some((r) => r.role_key === k));
  if (valid.length >= 2) {
    groupRoleSelection.value = roles.value.map((r) => r.role_key).filter((k) => valid.includes(k)).slice(0, 3);
    return;
  }
  const preferred = ["li_gan", "ban_chao", "shang_guan", "geng_gong", "zhang_qian", "fu_jiezi"];
  const picked: string[] = [];
  for (const k of preferred) {
    if (list.some((r) => r.role_key === k)) picked.push(k);
    if (picked.length >= 3) break;
  }
  for (const r of list) {
    if (picked.length >= 3) break;
    if (!picked.includes(r.role_key)) picked.push(r.role_key);
  }
  groupRoleSelection.value = picked.slice(0, 3);
}

function toggleGroupRole(key: string, checked: boolean) {
  const set = new Set(groupRoleSelection.value);
  if (checked) {
    if (set.size >= 3) {
      ElMessage.warning("群席最多三位同时出场");
      return;
    }
    set.add(key);
  } else {
    if (set.size <= 2) {
      ElMessage.warning("群席至少两人同席");
      return;
    }
    set.delete(key);
  }
  groupRoleSelection.value = roles.value.map((r) => r.role_key).filter((k) => set.has(k));
}

async function loadRoles() {
  try {
    const { data } = await http.get("/chat/roles");
    roles.value = (data.items as RoleItem[]) || [];
  } catch {
    roles.value = [];
  }
  ensureDefaultGroupSelection();
}

async function loadSessions() {
  const { data } = await http.get("/chat/sessions");
  sessions.value = data.items;
  if (!activeId.value && sessions.value.length) {
    activeId.value = sessions.value[0].id;
    await loadMessages();
  }
}

async function newSession(roleKey: string) {
  const r = roles.value.find((x) => x.role_key === roleKey);
  const title = r?.card_title || "边塞夜话";
  const { data } = await http.post("/chat/sessions", {
    role_key: roleKey,
    title,
    mode: "single",
  });
  sessions.value.unshift(data);
  activeId.value = data.id;
  messages.value = [];
  clearPoseTimer();
  avatarPose.value = "idle";
}

async function newGroupSession() {
  const keys = roles.value.map((r) => r.role_key).filter((k) => groupRoleSelection.value.includes(k));
  if (keys.length < 2) {
    ElMessage.warning("请至少选择两位人物再开群席");
    return;
  }
  const { data } = await http.post("/chat/sessions", {
    mode: "group",
    title: "群儒夜话",
    role_keys: keys.slice(0, 3),
  });
  sessions.value.unshift(data);
  activeId.value = data.id;
  messages.value = [];
  clearPoseTimer();
  avatarPose.value = "idle";
}

async function loadMessages() {
  if (!activeId.value) return;
  const { data } = await http.get(`/chat/sessions/${activeId.value}/messages`);
  messages.value = data.items;
}

async function selectSession(id: number) {
  activeId.value = id;
  clearPoseTimer();
  avatarPose.value = "idle";
  await loadMessages();
}

function bubbleLabel(m: { role: string; content: string }) {
  if (m.role === "user") return "我";
  const s = sessions.value.find((x) => x.id === activeId.value);
  if (s?.chat_mode === "group" && m.content.startsWith("【")) {
    const end = m.content.indexOf("】");
    if (end > 0) return m.content.slice(1, end);
  }
  if (s?.chat_mode === "single" && s.role_key) {
    return labelByKey.value[s.role_key] || "夜话";
  }
  return s?.chat_mode === "group" ? "夜话" : "夜话";
}

async function send() {
  if (!activeId.value) {
    ElMessage.warning("请先「新开一席」");
    return;
  }
  const t = input.value.trim();
  if (!t) return;
  sending.value = true;
  clearPoseTimer();
  avatarPose.value = "thinking";
  input.value = "";
  messages.value.push({ role: "user", content: t });
  try {
    const { data } = await http.post(`/chat/sessions/${activeId.value}/messages`, { content: t });
    let replyText = "";
    if (data.mode === "group" && Array.isArray(data.replies)) {
      for (const r of data.replies as Array<{ label: string; reply: string }>) {
        messages.value.push({ role: "assistant", content: `【${r.label}】${r.reply}` });
        replyText += r.reply;
      }
    } else if (data.reply) {
      messages.value.push({ role: "assistant", content: data.reply });
      replyText = String(data.reply);
    }
    if (replyText.length > 0) {
      avatarPose.value = "speaking";
      const ms = Math.min(14000, Math.max(3200, 1600 + replyText.length * 42));
      scheduleReturnToIdle(ms);
    } else {
      avatarPose.value = "idle";
    }
  } catch {
    ElMessage.error("尺牍未达，请稍后再试");
    messages.value.pop();
    avatarPose.value = "idle";
  } finally {
    sending.value = false;
  }
}

onMounted(async () => {
  const saved = localStorage.getItem("dj_chat_show_3d");
  if (saved === "0") show3d.value = false;
  await loadRoles();
  await loadSessions();
});

watch(show3d, (v) => {
  localStorage.setItem("dj_chat_show_3d", v ? "1" : "0");
});

onBeforeUnmount(() => {
  clearPoseTimer();
});
</script>

<template>
  <div class="page dj-page chat-page">
    <header class="chat-hero">
      <span class="dj-kicker chat-kicker">沉浸式夜话</span>
      <h1 class="dj-heading chat-h1">边塞夜话</h1>
      <p class="intro">
        可与戍卒、刀笔吏等身份对谈，亦可选择班超、耿恭、张骞、傅介子等史传人物（人设侧重常识与语气，非戏说传记）。开启<strong>烽影三维</strong>时，单席与群席均可并列呈现小影，并随问对呈现待机、凝思与对谈节奏。「群儒夜话」可在左侧自选 2～3 人同席，依次答问。
      </p>
    </header>
    <el-row :gutter="12">
      <el-col :xs="24" :sm="7" :md="6">
        <el-card class="dj-slip-card side">
          <div class="new-block">
            <div class="new-label">新开一席（任选一人）</div>
            <div class="role-btns">
              <el-button
                v-for="r in roles"
                :key="r.role_key"
                type="primary"
                plain
                class="role-btn"
                @click="newSession(r.role_key)"
              >
                <ChatPortraitImg :role-key="r.role_key" class="role-thumb" alt="" width="28" height="36" />
                <span class="role-btn-text">{{ r.card_title }}</span>
              </el-button>
            </div>
            <div class="group-block mt-sm">
              <div class="group-label">群儒夜话（自选 2～3 人）</div>
              <div class="group-checks">
                <el-checkbox
                  v-for="r in roles"
                  :key="r.role_key"
                  :model-value="groupRoleSelection.includes(r.role_key)"
                  class="group-check"
                  @change="(v: boolean | string | number) => toggleGroupRole(r.role_key, v === true)"
                >
                  {{ r.card_title }}
                </el-checkbox>
              </div>
              <el-button class="full" type="primary" @click="newGroupSession">开启群席</el-button>
            </div>
          </div>
          <el-menu :default-active="String(activeId || '')" class="mt">
            <el-menu-item
              v-for="s in sessions"
              :key="s.id"
              :index="String(s.id)"
              @click="selectSession(s.id)"
            >
              <span class="sess-title">{{ s.title }}</span>
              <el-tag v-if="s.chat_mode === 'group'" size="small" class="sess-tag">群聊</el-tag>
            </el-menu-item>
          </el-menu>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="17" :md="18">
        <el-card class="chat-card dj-slip-card chat-main-card">
          <div v-if="activeId" class="stage-toolbar">
            <p v-if="show3d" class="pose-hint" :data-pose="avatarPose">{{ stagePoseHint }}</p>
            <p v-else class="pose-hint muted">绢本立绘</p>
            <el-switch
              v-model="show3d"
              class="show-3d-switch"
              active-text="烽影三维"
              inactive-text="绢本立绘"
            />
          </div>
          <ChatRoleStage
            v-if="activeId && roles.length"
            :roles-catalog="roles"
            :primary-role-key="stagePrimaryKey"
            :is-group="stageIsGroup"
            :group-role-keys="stageGroupKeys"
            :show-3d="show3d"
            :avatar-pose="avatarPose"
          />
          <el-alert
            v-else-if="!activeId"
            title="请先在左侧「新开一席」或选择已有会话，即可显示本席立绘与可选三维小影。"
            type="info"
            :closable="false"
            class="stage-placeholder"
            show-icon
          />
          <div class="thread">
            <div v-for="(m, i) in messages" :key="i" :class="['bubble', m.role]">
              <span class="who">{{ bubbleLabel(m) }}</span>
              {{ m.content }}
            </div>
            <div v-if="sending" class="bubble assistant bubble--typing" role="status" aria-live="polite">
              <span class="who">候答</span>
              <span class="ink-wave" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              <span class="visually-hidden">牍师正在缮写</span>
            </div>
            <el-empty v-if="!messages.length && !sending" description="择一席，问禀食、西域、律令、边城旧事" />
          </div>
          <div class="composer">
            <el-input
              v-model="input"
              type="textarea"
              :rows="3"
              placeholder="可问禀食、候长文书、烽燧值守、西域行程……"
              @keydown.enter.exact.prevent="send"
            />
            <el-button type="primary" :loading="sending" class="send" @click="send">传书</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 36px;
}
.chat-hero {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(110, 88, 58, 0.1);
}
.chat-kicker {
  margin-bottom: 4px;
}
.chat-h1 {
  font-size: 24px;
  margin: 0 0 12px;
  letter-spacing: 0.08em;
  font-weight: 600;
}
.intro {
  margin: 0;
  max-width: 52em;
  font-size: 14px;
  color: var(--dj-ink-soft);
  line-height: 1.7;
}
.intro strong {
  font-weight: 600;
  color: var(--dj-ink, #3d3028);
}
.chat-main-card :deep(.el-card__body) {
  padding: 16px 18px 18px;
}
.side :deep(.el-menu) {
  border-right: none;
  background: transparent;
}
.new-block {
  margin-bottom: 8px;
}
.new-label {
  font-size: 12px;
  color: var(--dj-ink-soft);
  margin-bottom: 8px;
}
.role-btns {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.role-btn {
  width: 100%;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  height: auto;
  padding: 8px 12px;
}
.role-thumb {
  flex-shrink: 0;
  border-radius: 4px;
  object-fit: cover;
}
.role-btn-text {
  text-align: left;
}
.full {
  width: 100%;
}
.mt-sm {
  margin-top: 8px;
}
.group-block {
  padding-top: 10px;
  border-top: 1px dashed rgba(110, 88, 58, 0.14);
}
.group-label {
  font-size: 12px;
  color: var(--dj-ink-soft);
  margin-bottom: 8px;
}
.group-checks {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.group-check {
  margin: 0;
  height: auto;
  align-items: flex-start;
}
.group-check :deep(.el-checkbox__label) {
  font-size: 13px;
  line-height: 1.45;
  white-space: normal;
}
.mt {
  margin-top: 12px;
}
.sess-title {
  vertical-align: middle;
}
.sess-tag {
  margin-left: 6px;
  vertical-align: middle;
}
.stage-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(110, 88, 58, 0.12);
}
.pose-hint {
  margin: 0;
  flex: 1;
  min-width: 12em;
  font-size: 12px;
  letter-spacing: 0.06em;
  color: var(--dj-bamboo, #6b5344);
  line-height: 1.5;
  transition: color 0.3s ease;
}
.pose-hint[data-pose="thinking"] {
  color: #5a6b8a;
}
.pose-hint[data-pose="speaking"] {
  color: #8b5a2b;
}
.pose-hint.muted {
  color: var(--dj-ink-soft);
  opacity: 0.85;
}
.show-3d-switch :deep(.el-switch__label) {
  font-size: 12px;
  letter-spacing: 0.04em;
}
.stage-placeholder {
  margin-bottom: 12px;
}
.chat-card {
  min-height: 440px;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  box-shadow: 0 10px 40px rgba(48, 32, 18, 0.06);
}
.thread {
  flex: 1;
  max-height: min(54vh, 500px);
  overflow-y: auto;
  padding: 10px 6px 18px;
  scroll-behavior: smooth;
}
.bubble {
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.68;
  font-size: 14px;
  max-width: 92%;
  box-shadow: 0 2px 12px rgba(48, 32, 18, 0.04);
}
.bubble.user {
  margin-left: auto;
  background: linear-gradient(135deg, rgba(212, 165, 116, 0.42) 0%, rgba(212, 165, 116, 0.22) 100%);
  border: 1px solid rgba(139, 90, 43, 0.22);
  color: var(--dj-ink);
}
.bubble.assistant {
  position: relative;
  margin-right: auto;
  padding-left: 38px;
  background: linear-gradient(145deg, rgba(232, 220, 200, 0.95) 0%, rgba(212, 190, 160, 0.45) 100%);
  border: 1px solid rgba(139, 90, 43, 0.18);
  color: var(--dj-ink);
}
.bubble.assistant:not(.bubble--typing)::before {
  content: "牍";
  position: absolute;
  left: 10px;
  top: 14px;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--dj-font-display, serif);
  font-size: 12px;
  font-weight: 700;
  color: rgba(139, 90, 43, 0.85);
  border-radius: 4px;
  border: 1px solid rgba(139, 90, 43, 0.28);
  background: rgba(255, 252, 248, 0.75);
}
.bubble--typing .ink-wave {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-left: 4px;
  vertical-align: middle;
}
.bubble--typing .ink-wave span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(62, 58, 57, 0.45);
  animation: dj-ink-wave 1.1s ease-in-out infinite;
}
.bubble--typing .ink-wave span:nth-child(2) {
  animation-delay: 0.15s;
}
.bubble--typing .ink-wave span:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes dj-ink-wave {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.35;
  }
  50% {
    transform: translateY(-4px);
    opacity: 0.95;
  }
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
@media (prefers-reduced-motion: reduce) {
  .bubble--typing .ink-wave span {
    animation: none;
    opacity: 0.55;
  }
}
.who {
  display: block;
  font-size: 11px;
  color: var(--dj-bamboo);
  margin-bottom: 4px;
  letter-spacing: 0.08em;
}
.composer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px dashed rgba(110, 88, 58, 0.14);
}
.composer :deep(.el-textarea__inner) {
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.6;
}
.send {
  align-self: flex-end;
}
</style>
