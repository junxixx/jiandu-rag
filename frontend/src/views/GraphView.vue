<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts";
import http from "@/api/http";
import { ElMessage } from "element-plus";

type GraphApiNode = {
  id: string;
  name: string;
  category?: string;
  slip_id?: number;
  slip_code?: string;
};

type GraphEdge = { source: string; target: string; rel?: string };

/** 力导向 / 环形 / 高斥力：避免单一「拉成一条线」观感 */
type GraphLayoutMode = "force" | "circular" | "forceWide";

const router = useRouter();
const chartRef = ref<HTMLDivElement | null>(null);
const chart = shallowRef<echarts.ECharts | null>(null);
const source = ref("");
const loading = ref(false);
const nodeLimit = ref(100);
/** 默认显示遗址连线：多数子图仅有简牍—遗址关系，隐藏会导致整图无边、画布空白 */
const hideAtSite = ref(false);
const filterSite = ref("");
const filterTag = ref("");
const filterSlipCode = ref("");
const filterSlipId = ref("");

const layoutMode = ref<GraphLayoutMode>("force");
const graphFallbackNote = ref("");
const lastNodes = ref<GraphApiNode[]>([]);
const lastEdges = ref<GraphEdge[]>([]);

const sourceLabel = computed(() => {
  const s = source.value;
  if (!s) return "—";
  if (/neo4j/i.test(s)) return "编联图谱";
  return "图谱";
});

/** 图例顺序与颜色固定，避免与节点语义错位 */
const CATEGORY_ORDER = [
  { key: "Slip", name: "简牍", color: "#3d6ea8" },
  { key: "Site", name: "遗址", color: "#4a8f62" },
  { key: "Corpus", name: "影像语料", color: "#2f7d6d" },
  { key: "CorpusBatch", name: "数据子集", color: "#5a9aa8" },
  { key: "Tag", name: "标签", color: "#c9a227" },
  { key: "Event", name: "史事", color: "#7c5cbf" },
  { key: "Person", name: "人物", color: "#8b4a2e" },
] as const;

function symbolSizeFor(label: string | undefined): number {
  switch (label) {
    case "Site":
      return 26;
    case "Corpus":
      return 24;
    case "CorpusBatch":
      return 19;
    case "Slip":
      return 11;
    case "Person":
      return 17;
    case "Tag":
      return 15;
    case "Event":
      return 16;
    default:
      return 13;
  }
}

function buildCategories(nodes: Array<{ category?: string }>) {
  const used = new Set(nodes.map((n) => n.category || "Slip"));
  const ordered = CATEGORY_ORDER.filter((c) => used.has(c.key));
  const extras = [...used].filter((k) => !CATEGORY_ORDER.some((c) => c.key === k));
  const tail = extras.map((k) => ({ key: k, name: k, color: "#6b7280" }));
  return [...ordered, ...tail];
}

function buildOption(nodes: GraphApiNode[], edges: GraphEdge[], mode: GraphLayoutMode) {
  const cats = buildCategories(nodes);
  const catIndex = (label: string | undefined) => {
    const k = label || "Slip";
    const i = cats.findIndex((c) => c.key === k);
    return i >= 0 ? i : 0;
  };
  const nData = nodes.map((n) => {
    const idx = catIndex(n.category);
    const row: Record<string, unknown> = {
      id: n.id,
      name: n.name,
      category: idx,
      symbolSize: symbolSizeFor(n.category),
      itemStyle: { color: cats[idx]?.color ?? "#6b7280" },
    };
    if (n.slip_id != null) row.slip_id = n.slip_id;
    if (n.slip_code) row.slip_code = n.slip_code;
    return row;
  });
  const eData = edges.map((e, i) => ({
    source: e.source,
    target: e.target,
    rel: e.rel,
    label: { show: false },
    lineStyle:
      mode === "circular"
        ? { curveness: 0.15 + (i % 5) * 0.04, opacity: 0.5 }
        : { curveness: 0.12, opacity: 0.45 },
  }));
  const catNames = cats.map((c) => ({ name: c.name }));

  const layoutSeries =
    mode === "circular"
      ? {
          layout: "circular" as const,
          circular: { rotateLabel: true },
        }
      : mode === "forceWide"
        ? {
            layout: "force" as const,
            force: {
              repulsion: 1280,
              edgeLength: [88, 200],
              gravity: 0.045,
              friction: 0.86,
            },
          }
        : {
            layout: "force" as const,
            force: {
              repulsion: 720,
              edgeLength: [64, 150],
              gravity: 0.075,
              friction: 0.88,
            },
          };

  return {
    backgroundColor: "transparent",
    tooltip: {
      backgroundColor: "rgba(255, 251, 243, 0.95)",
      borderColor: "#c9b08a",
      textStyle: { color: "#2a2218", fontSize: 12 },
      formatter: (p: {
        dataType?: string;
        data?: { name?: string; category?: number; rel?: string; slip_id?: number };
        name?: string;
      }) => {
        if (p.dataType === "edge") {
          const d = p.data as { rel?: string };
          return (d?.rel || "关系") as string;
        }
        const d = p.data as { name?: string; category?: number; slip_id?: number };
        const typeName = cats[d?.category ?? 0]?.name ?? "";
        const title = d?.name ?? p.name ?? "";
        const hint = d?.slip_id != null ? "<br/><span style='opacity:.75'>单击跳转牍库详情</span>" : "";
        return `${typeName}<br/>${title}${hint}`;
      },
    },
    legend: {
      data: cats.map((c) => c.name),
      bottom: 0,
      textStyle: { color: "#4a3f32", fontFamily: "Noto Serif SC, SimSun, serif" },
    },
    series: [
      {
        type: "graph",
        roam: true,
        draggable: true,
        ...layoutSeries,
        label: {
          show: false,
          position: "right",
          fontSize: 11,
          color: "#2a2218",
          fontFamily: "Noto Serif SC, SimSun, serif",
        },
        emphasis: {
          focus: "adjacency",
          label: { show: true, fontSize: 11 },
          lineStyle: { width: 2, opacity: 1 },
        },
        blur: {
          itemStyle: { opacity: 0.35 },
          lineStyle: { opacity: 0.2 },
        },
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [0, 9],
        categories: catNames,
        data: nData,
        links: eData,
        lineStyle: {
          color: "#a67c52",
          width: 1,
        },
      },
    ],
  };
}

function applyLayoutFromCache() {
  if (!chart.value || !lastNodes.value.length) return;
  chart.value.setOption(buildOption(lastNodes.value, lastEdges.value, layoutMode.value), {
    notMerge: true,
  });
  bindChartClick();
}

watch(layoutMode, () => {
  applyLayoutFromCache();
});

function bindChartClick() {
  if (!chart.value) return;
  chart.value.off("click");
  chart.value.on("click", (raw) => {
    const params = raw as { dataType?: string; data?: { slip_id?: number } | null };
    if (params.dataType !== "node") return;
    const sid = params.data?.slip_id;
    if (sid != null) {
      router.push({ name: "slip", params: { id: String(sid) } }).catch(() => {});
    }
  });
}

function clearFilters() {
  filterSite.value = "";
  filterTag.value = "";
  filterSlipCode.value = "";
  filterSlipId.value = "";
}

function subgraphParams(): Record<string, string | number> {
  const p: Record<string, string | number> = {
    limit: nodeLimit.value,
    no_site: hideAtSite.value ? 1 : 0,
  };
  const fs = filterSite.value.trim();
  if (fs) p.site = fs;
  const ft = filterTag.value.trim();
  if (ft) p.tag = ft;
  const fc = filterSlipCode.value.trim();
  if (fc) p.slip_code = fc;
  const fid = filterSlipId.value.trim();
  if (fid && /^\d+$/.test(fid)) p.slip_id = parseInt(fid, 10);
  return p;
}

async function load() {
  loading.value = true;
  graphFallbackNote.value = "";
  try {
    const { data } = await http.get("/graph/subgraph", { params: subgraphParams() });
    source.value = data.source;
    if (data.site_edges_fallback) {
      hideAtSite.value = false;
      graphFallbackNote.value =
        "当前子图主要为简牍与遗址的关联；已自动纳入遗址连线以便成图。若需减轻星形拥挤，可在数据补充标签/人物关系后再尝试隐藏遗址连线。";
    }
    if (!chartRef.value) return;
    if (!chart.value) chart.value = echarts.init(chartRef.value);
    bindChartClick();
    if (!data.nodes?.length) {
      chart.value.clear();
      lastNodes.value = [];
      lastEdges.value = [];
      ElMessage.info(
        hideAtSite.value && !filterSite.value.trim() && !filterTag.value.trim()
          ? "当前条件下暂无关系（可关闭「隐藏遗址连线」、调整筛选或增大节点上限后重试）"
          : "图谱暂无节点，可放宽筛选、提高节点上限，或在站务中同步牍库至图谱"
      );
      return;
    }
    lastNodes.value = data.nodes as GraphApiNode[];
    lastEdges.value = (data.edges || []) as GraphEdge[];
    chart.value.setOption(
      buildOption(lastNodes.value, lastEdges.value, layoutMode.value),
      { notMerge: true }
    );
    bindChartClick();
  } catch {
    ElMessage.error("图谱加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  load();
  window.addEventListener("resize", resize);
});
onUnmounted(() => {
  window.removeEventListener("resize", resize);
  chart.value?.dispose();
});

function resize() {
  chart.value?.resize();
}
</script>

<template>
  <div class="page dj-page">
    <span class="dj-kicker graph-kicker">编联可视</span>
    <h1 class="dj-heading graph-h1">简牍图谱</h1>
    <p class="intro">
      本图将<strong>简牍、遗址、人物、主题与史事</strong>编联为一张可交互的网络：节点可拖拽缩放，<strong>单击简牍</strong>即入牍库详情。
      牍库条目中若以「人:姓名」「人物:姓名」（半角或全角冒号均可）标注，则与人物相连；其余逗号分隔片段多为主题标签。
      下方可按<strong>遗址名、标签名、简牍编号或编号 ID</strong>收束视野。<strong>隐藏遗址连线</strong>不会隐藏「影像语料」类节点（DeepJiandu 等无考古出土地时，图谱以数据集与子集编联，并非冒充遗址）。
      「画布与连线」中可切换<strong>力导向 / 环形 / 松斥力</strong>三种布局。数据需在站务中自牍库同步至图谱后方可呈现。
    </p>
    <p v-if="graphFallbackNote" class="graph-fallback" role="status">{{ graphFallbackNote }}</p>
    <div class="tool-wrap">
      <section class="tool-group" aria-labelledby="graph-filter-title">
        <h2 id="graph-filter-title" class="tool-group-title">收束视野</h2>
        <div class="tool-group-body tool-group-body--filters">
          <el-input v-model="filterSite" clearable placeholder="遗址名" class="f-inp" />
          <el-input v-model="filterTag" clearable placeholder="标签名（精确）" class="f-inp" />
          <el-input v-model="filterSlipCode" clearable placeholder="简牍编号 code" class="f-inp" />
          <el-input v-model="filterSlipId" clearable placeholder="简牍 ID（数字）" class="f-inp narrow" />
          <el-button size="small" plain type="primary" @click="clearFilters">清空条件</el-button>
        </div>
      </section>

      <section class="tool-group" aria-labelledby="graph-display-title">
        <h2 id="graph-display-title" class="tool-group-title">画布与连线</h2>
        <div class="tool-group-body tool-group-body--display">
          <div class="ctl-row">
            <span class="ctl-label">节点上限</span>
            <el-slider v-model="nodeLimit" :min="40" :max="280" :step="20" class="limit-slider" />
            <span class="ctl-num">{{ nodeLimit }}</span>
          </div>
          <div class="ctl-row ctl-row--layout">
            <span class="ctl-label">布局</span>
            <el-radio-group v-model="layoutMode" size="small" class="layout-rg">
              <el-radio-button label="force">力导向</el-radio-button>
              <el-radio-button label="circular">环形</el-radio-button>
              <el-radio-button label="forceWide">松斥力</el-radio-button>
            </el-radio-group>
          </div>
          <el-switch v-model="hideAtSite" active-text="隐藏遗址连线" inactive-text="显示遗址连线" class="sw" />
        </div>
      </section>

      <section class="tool-group tool-group--action" aria-labelledby="graph-action-title">
        <h2 id="graph-action-title" class="tool-group-title">操作</h2>
        <div class="tool-group-body tool-group-body--action">
          <span class="tag">图谱来源：<em>{{ sourceLabel }}</em></span>
          <el-button size="small" type="primary" :loading="loading" @click="load">重绘图谱</el-button>
        </div>
      </section>
    </div>
    <div
      ref="chartRef"
      class="chart"
      role="application"
      aria-label="简牍知识图谱，可用鼠标拖拽与滚轮缩放"
      tabindex="0"
    />
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 32px;
}
.graph-kicker {
  margin-bottom: 4px;
}
.graph-h1 {
  font-size: 22px;
  margin: 0 0 12px;
  letter-spacing: 0.06em;
}
.intro {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--dj-ink-soft);
  line-height: 1.6;
}
.intro code {
  font-size: 12px;
  padding: 0 4px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.06);
}
.graph-fallback {
  margin: 0 0 12px;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--dj-ink-soft);
  border-radius: var(--dj-radius-sm, 10px);
  border: 1px dashed rgba(166, 124, 82, 0.55);
  background: rgba(255, 251, 243, 0.85);
}
html.dark .intro code {
  background: rgba(255, 255, 255, 0.08);
}
html.dark .graph-fallback {
  background: rgba(42, 34, 24, 0.35);
  border-color: rgba(201, 176, 138, 0.35);
}
.tool-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 16px;
  align-items: stretch;
}
.tool-group {
  flex: 1 1 280px;
  min-width: min(100%, 260px);
  padding: 14px 16px 16px;
  border-radius: var(--dj-radius-sm, 10px);
  border: 1px solid rgba(201, 176, 138, 0.45);
  background: linear-gradient(
    165deg,
    rgba(255, 251, 243, 0.96) 0%,
    rgba(252, 246, 234, 0.88) 45%,
    rgba(239, 226, 204, 0.35) 100%
  );
  box-shadow: 0 6px 22px rgba(42, 34, 24, 0.06);
  transition: box-shadow 0.25s ease, border-color 0.25s ease;
}
.tool-group:hover {
  border-color: rgba(166, 124, 82, 0.35);
  box-shadow: 0 10px 28px rgba(42, 34, 24, 0.08);
}
.tool-group--action {
  flex: 1 1 220px;
  min-width: min(100%, 200px);
}
.tool-group-title {
  margin: 0 0 10px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--dj-border-light);
  font-family: var(--dj-font-display);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--dj-ink-soft);
}
.tool-group-body {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.tool-group-body--filters {
  align-items: flex-start;
}
.tool-group-body--display {
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
}
.tool-group-body--action {
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
}
.ctl-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  width: 100%;
}
.ctl-row--layout {
  align-items: flex-start;
}
.layout-rg {
  flex: 1;
  min-width: 0;
}
.f-inp {
  width: 200px;
  max-width: 100%;
}
.f-inp.narrow {
  width: 140px;
}
.ctl-label {
  font-size: 13px;
  color: var(--dj-ink-soft);
  white-space: nowrap;
}
.limit-slider {
  flex: 1;
  max-width: 240px;
  min-width: 120px;
}
.ctl-num {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-color-primary);
  width: 2.2em;
}
.sw {
  align-self: flex-start;
}
.tag {
  font-size: 13px;
  color: var(--dj-ink-soft);
}
.tag em {
  font-style: normal;
  color: var(--el-color-primary);
  font-weight: 600;
}
.chart {
  height: 560px;
  background: linear-gradient(180deg, rgba(255, 251, 243, 0.95) 0%, rgba(239, 226, 204, 0.5) 100%);
  border-radius: 8px;
  border: 1px solid var(--dj-border-light);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.5);
}
</style>
