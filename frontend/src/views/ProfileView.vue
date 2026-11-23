<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import * as echarts from "echarts";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";
import { ElMessage } from "element-plus";

const auth = useAuthStore();
const tasks = ref<Array<{ code: string; title: string; points_reward: number; completed: boolean }>>([]);
const progress = ref<Array<{ slip_id: number; read_at: string }>>([]);

type BadgeDef = { code: string; title: string; description: string; icon: string | null };
const catalog = ref<BadgeDef[]>([]);
const earnedCodes = ref<Set<string>>(new Set());

const earnedList = computed(() => catalog.value.filter((b) => earnedCodes.value.has(b.code)));

type LearningMap = {
  stats: {
    slips_read: number;
    quiz_attempts: number;
    quiz_correct: number;
    quiz_accuracy: number;
    posts: number;
    comments: number;
    badges: number;
    checkin_streak: number;
  };
  radar: { dimensions: string[]; values: number[] };
};
const learningMap = ref<LearningMap | null>(null);
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
const checkinLoading = ref(false);

async function load() {
  const me = await http.get("/user/me");
  auth.user = me.data;
  const t = await http.get("/tasks/daily");
  tasks.value = t.data.items;
  const p = await http.get("/user/progress");
  progress.value = p.data.items;

  try {
    const [c, m] = await Promise.all([http.get("/public/badges"), http.get("/user/badges")]);
    catalog.value = c.data.items || [];
    earnedCodes.value = new Set((m.data.items || []).map((x: { code: string }) => x.code));
  } catch {
    catalog.value = [];
  }

  if (auth.token) {
    try {
      const { data } = await http.get<LearningMap>("/user/learning-map");
      learningMap.value = data;
      await nextTick();
      renderChart();
    } catch {
      learningMap.value = null;
    }
  } else {
    learningMap.value = null;
    chart?.dispose();
    chart = null;
  }
}

function renderChart() {
  if (!chartRef.value || !learningMap.value) return;
  const { dimensions, values } = learningMap.value.radar;
  if (!chart) chart = echarts.init(chartRef.value);
  chart.setOption({
    color: ["#9a3412"],
    radar: {
      indicator: dimensions.map((name) => ({ name, max: 100 })),
      splitArea: { areaStyle: { color: ["rgba(239,226,204,0.15)", "rgba(255,251,243,0.4)"] } },
    },
    series: [
      {
        type: "radar",
        data: [{ value: values, name: "学习维度", areaStyle: { opacity: 0.25 } }],
      },
    ],
  });
}

function onResize() {
  chart?.resize();
}

async function completeTask(code: string) {
  await http.post("/tasks/complete", { task_code: code });
  ElMessage.success("功不唐捐，积分已记于册");
  load();
}

async function doCheckin() {
  if (!auth.token) {
    ElMessage.warning("请先登录再打卡");
    return;
  }
  checkinLoading.value = true;
  try {
    const { data } = await http.post<{
      ok: boolean;
      already?: boolean;
      streak_days: number;
      points_delta?: number;
      milestone_bonus?: boolean;
    }>("/user/checkin");
    if (data.already) {
      ElMessage.info(`今日已打卡，已连续 ${data.streak_days} 天`);
    } else {
      const bonus = data.milestone_bonus ? "（含连续打卡里程碑加成）" : "";
      ElMessage.success(`打卡成功 +${data.points_delta ?? 0} 分，已连续 ${data.streak_days} 天${bonus}`);
    }
    await load();
  } catch {
    ElMessage.error("打卡失败");
  } finally {
    checkinLoading.value = false;
  }
}

function copyInvite() {
  const code = auth.user?.invite_code;
  if (!code) {
    ElMessage.info("邀请码尚未生成，可点「生成」补发");
    return;
  }
  navigator.clipboard.writeText(code).then(
    () => ElMessage.success("邀请码已复制"),
    () => ElMessage.error("复制失败")
  );
}

async function ensureInvite() {
  if (!auth.token) return;
  try {
    const { data } = await http.post<{ ok: boolean; invite_code?: string }>("/user/invite-code");
    if (data.invite_code) {
      auth.user = { ...(auth.user as any), invite_code: data.invite_code };
      ElMessage.success("邀请码已生成");
    }
  } catch {
    ElMessage.error("邀请码生成失败");
  }
}

watch(
  () => auth.token,
  () => load()
);

onMounted(() => {
  load();
  window.addEventListener("resize", onResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", onResize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="page dj-page">
    <el-card class="dj-slip-card profile-head">
      <h2 class="dj-heading">{{ auth.user?.nickname }}</h2>
      <p class="sub">
        简册积分：<strong>{{ auth.user?.points }}</strong>（读牍、答题、雅集击节皆可累之）
      </p>
      <div v-if="auth.token" class="invite-row">
        <span class="lbl">我的邀请码</span>
        <code class="code">{{ auth.user?.invite_code || "生成中…" }}</code>
        <el-button size="small" type="primary" plain @click="copyInvite">复制</el-button>
        <el-button v-if="!auth.user?.invite_code" size="small" type="primary" plain @click="ensureInvite">生成</el-button>
        <el-button size="small" :loading="checkinLoading" type="primary" @click="doCheckin">今日打卡</el-button>
        <span v-if="learningMap" class="streak">连续 {{ learningMap.stats.checkin_streak }} 天</span>
      </div>
    </el-card>

    <el-card v-if="auth.token && learningMap" class="mt dj-slip-card">
      <template #header>学习地图 · 能力雷达</template>
      <p class="hint">从读牍、问答、雅集、徽章与连续打卡等维度，归一为一张能力雷达（0–100），便于一览学程。</p>
      <div ref="chartRef" class="radar-chart" />
      <ul class="stat-list">
        <li>展牍：{{ learningMap.stats.slips_read }} 枚</li>
        <li>答题：{{ learningMap.stats.quiz_correct }} / {{ learningMap.stats.quiz_attempts }}（正确率 {{ (learningMap.stats.quiz_accuracy * 100).toFixed(1) }}%）</li>
        <li>雅集：发帖 {{ learningMap.stats.posts }} · 跋尾 {{ learningMap.stats.comments }}</li>
        <li>徽章：{{ learningMap.stats.badges }} 枚</li>
      </ul>
    </el-card>

    <el-card class="mt dj-slip-card">
      <template #header>徽章墙</template>
      <p class="hint">完成展牍、日课、雅集、辩论等操作可逐步解锁；若徽章长期不更新，可联系站务核对数据。</p>
      <div class="badge-grid">
        <div
          v-for="b in catalog"
          :key="b.code"
          class="badge-cell"
          :class="{ locked: !earnedCodes.has(b.code) }"
          :aria-label="b.title + (earnedCodes.has(b.code) ? '已解锁' : '未解锁')"
        >
          <el-icon class="bicon" :size="28">
            <component :is="b.icon || 'Medal'" />
          </el-icon>
          <div class="btitle">{{ b.title }}</div>
          <div class="bdesc">{{ b.description }}</div>
        </div>
      </div>
      <p v-if="earnedList.length" class="earned-summary">已获 {{ earnedList.length }} / {{ catalog.length }} 枚</p>
    </el-card>

    <el-card class="mt dj-slip-card">
      <template #header>今日功课</template>
      <el-table :data="tasks" size="small" class="dj-table">
        <el-table-column prop="title" label="功课" />
        <el-table-column prop="points_reward" label="积分" width="80" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.completed" type="success">已毕</el-tag>
            <el-button v-else size="small" type="primary" @click="completeTask(row.code)">销号</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="mt dj-slip-card">
      <template #header>最近展牍</template>
      <ul class="plist">
        <li v-for="(r, i) in progress" :key="i">
          <router-link class="plink" :to="'/slip/' + r.slip_id">简牍 #{{ r.slip_id }}</router-link>
          · {{ r.read_at }}
        </li>
      </ul>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  padding: 12px 0;
}
.profile-head h2 {
  margin: 0 0 8px;
  font-size: 22px;
}
.sub {
  margin: 0 0 10px;
  color: var(--dj-ink-soft);
  font-size: 14px;
}
.sub strong {
  color: var(--dj-seal);
  font-size: 18px;
}
.invite-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  font-size: 14px;
}
.invite-row .lbl {
  color: var(--dj-ink-soft);
}
.invite-row .code {
  background: rgba(239, 226, 204, 0.45);
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 15px;
}
.streak {
  color: var(--dj-bamboo);
  font-size: 13px;
}
.radar-chart {
  width: 100%;
  height: 320px;
}
.stat-list {
  margin: 12px 0 0;
  padding-left: 1.2em;
  color: var(--dj-ink-soft);
  font-size: 14px;
  line-height: 1.85;
}
.mt {
  margin-top: 16px;
}
.hint {
  font-size: 13px;
  color: var(--dj-ink-soft);
  margin: 0 0 14px;
  line-height: 1.6;
}
.hint code {
  font-size: 12px;
  background: rgba(239, 226, 204, 0.5);
  padding: 1px 6px;
  border-radius: 4px;
}
.badge-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.badge-cell {
  padding: 12px 10px;
  border-radius: 8px;
  border: 1px solid var(--dj-border-light);
  text-align: center;
  background: rgba(255, 251, 243, 0.85);
}
.badge-cell.locked {
  opacity: 0.45;
  filter: grayscale(0.35);
}
.bicon {
  color: var(--el-color-primary);
  margin-bottom: 6px;
}
.btitle {
  font-family: var(--dj-font-display);
  font-weight: 600;
  font-size: 14px;
  color: var(--dj-ink);
}
.bdesc {
  font-size: 11px;
  color: var(--dj-ink-soft);
  line-height: 1.45;
  margin-top: 4px;
}
.earned-summary {
  margin: 14px 0 0;
  font-size: 13px;
  color: var(--dj-bamboo);
}
.plist {
  margin: 0;
  padding-left: 1.2em;
  color: var(--dj-ink-soft);
  font-size: 14px;
  line-height: 1.85;
}
.plink {
  color: var(--el-color-primary);
}
:deep(.dj-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
}
</style>
