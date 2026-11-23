<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

type StoryNode = { id: string; title: string; body: string; reward: number; next: string[] };
type StoryProg = {
  story_id: string;
  current_node: string;
  completed_nodes: string[];
  rewards_total: number;
  nodes: StoryNode[];
};

const storyProg = ref<StoryProg | null>(null);
const storyLoading = ref(false);

const currentStoryNode = computed(() => {
  if (!storyProg.value) return null;
  return storyProg.value.nodes.find((n) => n.id === storyProg.value!.current_node) || null;
});

const nextStoryChoices = computed(() => {
  const cur = currentStoryNode.value;
  if (!cur?.next?.length) return [];
  if (!storyProg.value) return [];
  return cur.next
    .map((id) => storyProg.value!.nodes.find((n) => n.id === id))
    .filter(Boolean) as StoryNode[];
});

type TaskItem = { code: string; title: string; points_reward: number; completed: boolean };

const quests = [
  {
    title: "戍边日志 · 序",
    desc: "在「每日一牍」读完今日释文并提交日课，仿佛戍卒记下一行木牍。",
    to: "/daily",
    btn: "前往每日一牍",
    taskCode: "quest_daily_slip",
  },
  {
    title: "烽燧夜问",
    desc: "在「边塞夜话」任选人物完成一轮问对（粮草、文书、西域史事皆可）。需登录。",
    to: "/chat",
    btn: "前往夜话",
    taskCode: "quest_night_chat",
  },
  {
    title: "雅集留痕",
    desc: "在「雅集论道」发帖或跋尾一则，与同好共编当代「论议牍」。",
    to: "/forum",
    btn: "前往雅集",
    taskCode: "quest_forum_post",
  },
] as const;

const taskMap = ref<Record<string, boolean>>({});
const loading = ref(false);

const activeStep = computed(() => {
  const i = quests.findIndex((q) => !taskMap.value[q.taskCode]);
  return i === -1 ? quests.length : i;
});

const allDone = computed(() => quests.every((q) => taskMap.value[q.taskCode]));

async function loadProgress() {
  if (!auth.token) {
    taskMap.value = {};
    return;
  }
  loading.value = true;
  try {
    const { data } = await http.get<{ items: TaskItem[] }>("/tasks/daily");
    const m: Record<string, boolean> = {};
    for (const it of data.items || []) {
      m[it.code] = !!it.completed;
    }
    taskMap.value = m;
  } catch {
    ElMessage.error("任务进度加载失败");
  } finally {
    loading.value = false;
  }
}

async function markDone(taskCode: string) {
  if (!auth.token) {
    ElMessage.warning("请先登录再记入进度");
    router.push({ name: "login", query: { redirect: "/quests" } });
    return;
  }
  try {
    const { data } = await http.post("/tasks/complete", { task_code: taskCode });
    if (data.already) {
      ElMessage.info("今日已领过此功");
    } else {
      ElMessage.success(`已记入，+${data.points_delta ?? 0} 简册积分`);
    }
    await loadProgress();
  } catch {
    ElMessage.error("提交失败，请联系站务确认功课模板已就绪");
  }
}

async function loadStory() {
  if (!auth.token) {
    storyProg.value = null;
    return;
  }
  storyLoading.value = true;
  try {
    const { data } = await http.get<StoryProg>("/story/progress");
    storyProg.value = data;
  } catch {
    storyProg.value = null;
  } finally {
    storyLoading.value = false;
  }
}

async function advanceStory(nextId: string) {
  try {
    const { data } = await http.post<StoryProg & { ok?: boolean; points_delta?: number; error?: string }>(
      "/story/action",
      { next_node_id: nextId }
    );
    if (data.ok === false) {
      ElMessage.error(data.error || "推进失败");
      return;
    }
    ElMessage.success(
      data.points_delta ? `剧情推进，节点奖励 +${data.points_delta} 简册积分` : "已更新剧情位置"
    );
    storyProg.value = {
      story_id: data.story_id ?? storyProg.value?.story_id ?? "shubian_log",
      current_node: data.current_node,
      completed_nodes: data.completed_nodes,
      rewards_total: data.rewards_total,
      nodes: data.nodes,
    };
  } catch {
    ElMessage.error("推进失败：请确认剧情存档服务可用后重试");
  }
}

watch(
  () => auth.token,
  () => {
    loadProgress();
    loadStory();
  }
);

onMounted(() => {
  loadProgress();
  loadStory();
});
</script>

<template>
  <div class="page dj-page">
    <p class="intro">
      将「每日一牍 → 边塞夜话 → 雅集论道」串成一条学习线；每完成一步，可在下方<strong>记入进度</strong>领取当日简册积分。若提示功课未就绪，请联系站务处理。
    </p>

    <el-card v-if="auth.token" v-loading="storyLoading" class="mb dj-slip-card">
      <template #header>戍边手记 · 剧情存档</template>
      <p v-if="!storyProg" class="muted">暂无法载入手记进度，请确认已登录且服务端剧情存档已开启。</p>
      <template v-else>
        <p class="story-meta">
          累计手记赏赐：<strong>{{ storyProg.rewards_total }}</strong> 分<span v-if="currentStoryNode"> · 此刻驻足：「{{ currentStoryNode.title }}」</span>
        </p>
        <h4 v-if="currentStoryNode" class="dj-heading">{{ currentStoryNode.title }}</h4>
        <p v-if="currentStoryNode" class="desc">{{ currentStoryNode.body }}</p>
        <div v-if="nextStoryChoices.length" class="row">
          <span class="lbl">下一程：</span>
          <el-button
            v-for="n in nextStoryChoices"
            :key="n.id"
            type="primary"
            plain
            size="small"
            @click="advanceStory(n.id)"
          >
            前往「{{ n.title }}」
          </el-button>
        </div>
        <p v-else-if="currentStoryNode" class="muted">已至本线末梢，可日日重来或待后续章节。</p>
      </template>
    </el-card>

    <el-skeleton v-if="loading && auth.token" :rows="4" animated class="sk" />

    <el-alert
      v-else-if="!auth.token"
      title="登录后可查看与勾选任务完成状态，并领取积分。"
      type="info"
      :closable="false"
      class="mb"
      show-icon
    />

    <el-steps v-else direction="vertical" :active="activeStep" finish-status="success" class="steps">
      <el-step v-for="q in quests" :key="q.taskCode" :title="q.title">
        <template #description>
          <p class="desc">{{ q.desc }}</p>
          <p class="status">
            <el-tag v-if="taskMap[q.taskCode]" type="success" size="small">今日已完成</el-tag>
            <el-tag v-else type="info" size="small">待完成</el-tag>
          </p>
          <div class="row">
            <el-button type="primary" link @click="router.push(q.to)">{{ q.btn }} →</el-button>
            <el-button
              v-if="!taskMap[q.taskCode]"
              type="primary"
              size="small"
              plain
              @click="markDone(q.taskCode)"
            >
              我已完成本步
            </el-button>
          </div>
        </template>
      </el-step>
    </el-steps>

    <el-result v-if="auth.token && allDone && !loading" icon="success" title="三章已毕" sub-title="今日戍边手记线已全部勾选。" />

    <el-card class="mt dj-slip-card hint">
      <template #header>说明</template>
      <ul class="ul">
        <li>「我已完成本步」依诚信勾选；后续可结合服务端记录自动校验。</li>
        <li>功课与徽章、简册积分一体贯通，由站务维护模板。</li>
        <li>手记剧情进度在云端存档，换设备登录亦可接续。</li>
      </ul>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  padding: 12px 0 24px;
}
.intro {
  margin: 0 0 20px;
  line-height: 1.75;
  color: var(--dj-ink-soft);
  font-size: 14px;
}
.intro code {
  font-size: 12px;
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 6px;
  border-radius: 4px;
}
html.dark .intro code {
  background: rgba(255, 255, 255, 0.08);
}
.mb {
  margin-bottom: 16px;
}
.story-meta {
  font-size: 13px;
  color: var(--dj-ink-soft);
  margin: 0 0 12px;
}
.story-meta strong {
  color: var(--dj-seal);
}
.muted {
  font-size: 13px;
  color: var(--dj-ink-soft);
  margin: 0;
}
.lbl {
  font-size: 13px;
  color: var(--dj-ink-soft);
  margin-right: 8px;
}
.sk {
  margin-bottom: 16px;
}
.steps {
  max-width: 640px;
  background: rgba(255, 251, 243, 0.6);
  padding: 20px 24px;
  border-radius: 8px;
  border: 1px solid var(--dj-border-light);
}
.desc {
  margin: 6px 0 8px;
  line-height: 1.65;
  color: var(--dj-ink);
  font-size: 14px;
}
.status {
  margin: 0 0 8px;
}
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.mt {
  margin-top: 20px;
}
.ul {
  margin: 0;
  padding-left: 1.2em;
  line-height: 1.8;
  color: var(--dj-ink-soft);
  font-size: 14px;
}
</style>
