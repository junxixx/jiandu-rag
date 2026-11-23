<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";
import { trackEvent } from "@/composables/track";
import { slipImageSrc } from "@/composables/slipImage";
import { useRouter } from "vue-router";

const auth = useAuthStore();
const router = useRouter();

type Item = { id: number; code: string; title: string; site_name: string | null; era: string | null; image_url: string | null };
type Detail = Item & { transcription: string; vernacular: string; tags: string | null };

const q = ref("");
const page = ref(1);
const size = ref(18);
const total = ref(0);
const items = ref<Item[]>([]);
const loading = ref(false);
/** 游标模式「还有下一批」；翻页搜索后会重置 */
const cursorHasMore = ref(false);

const drawer = ref(false);
const detail = ref<Detail | null>(null);
const detailLoading = ref(false);

async function load() {
  loading.value = true;
  try {
    const { data } = await http.get("/slips", {
      params: { page: page.value, size: size.value, q: q.value.trim() || undefined },
    });
    items.value = data.items;
    total.value = data.total ?? 0;
    cursorHasMore.value = false;
    trackEvent("slip_search", { q: q.value.trim() || null, page: page.value });
  } catch {
    ElMessage.error("牍库加载失败");
  } finally {
    loading.value = false;
  }
}

async function openDetail(row: Item) {
  drawer.value = true;
  detail.value = null;
  detailLoading.value = true;
  try {
    const { data } = await http.get(`/slips/${row.id}`);
    detail.value = data;
  } catch {
    ElMessage.error("详情加载失败");
  } finally {
    detailLoading.value = false;
  }
}

async function markRead() {
  if (!auth.token || !detail.value) {
    ElMessage.warning("登录后可记入「我的简册」阅读轨迹");
    return;
  }
  try {
    await http.post("/user/progress/read", { slip_id: detail.value.id });
    ElMessage.success("已记入掌阅");
  } catch {
    ElMessage.error("记录失败");
  }
}

function copyText(text: string) {
  navigator.clipboard.writeText(text).then(
    () => ElMessage.success("已复制到剪贴板"),
    () => ElMessage.error("复制失败")
  );
}

let timer: ReturnType<typeof setTimeout> | null = null;
function onQueryInput() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    page.value = 1;
    load();
  }, 400);
}

watch(page, () => load());

const showCursorMore = computed(() => {
  if (!items.value.length || loading.value) return false;
  if (cursorHasMore.value) return true;
  return total.value > items.value.length;
});

async function loadMoreCursor() {
  const last = items.value[items.value.length - 1];
  if (!last || loading.value) return;
  loading.value = true;
  try {
    const { data } = await http.get("/slips", {
      params: {
        after_id: last.id,
        size: size.value,
        q: q.value.trim() || undefined,
      },
    });
    items.value = [...items.value, ...data.items];
    cursorHasMore.value = !!data.has_more;
    trackEvent("slip_cursor_more", { q: q.value.trim() || null });
  } catch {
    ElMessage.error("连续加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page dj-page">
    <header class="browse-head">
      <span class="dj-kicker page-kicker">万卷牍库</span>
      <h1 class="dj-heading page-title">检索与展卷</h1>
      <p class="intro">
        按编号、标题或释文、白话中的词句寻牍；边塞爰书、乡里簿籍皆可检索。点选卡片即展全文，可一键复制释文；登录后亦可记入「我的简册」阅读轨迹。
      </p>
      <p class="intro intro-2">简牍卡片悬停时略浮起，便于扫览；若结果较多，可翻页或连续载入，直至尽览所求。</p>
    </header>

    <div class="toolbar dj-toolbar-strip">
      <el-input
        v-model="q"
        clearable
        placeholder="搜索编号、标题、释文、白话……"
        class="search"
        @input="onQueryInput"
        @clear="onQueryInput"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-skeleton v-if="loading && !items.length" :rows="6" animated />

    <div v-else class="grid">
      <el-card
        v-for="s in items"
        :key="s.id"
        class="cell dj-slip-card"
        shadow="hover"
        @click="openDetail(s)"
      >
        <div class="code">{{ s.code }}</div>
        <div v-if="slipImageSrc(s.image_url)" class="thumb-wrap">
          <img
            :src="slipImageSrc(s.image_url)"
            :alt="`简牍缩略图 ${s.code}`"
            class="thumb"
            loading="lazy"
          />
        </div>
        <div class="title">{{ s.title }}</div>
        <div v-if="s.site_name || s.era" class="meta">
          <span v-if="s.site_name" class="meta-item">{{ s.site_name }}</span>
          <span v-if="s.site_name && s.era" class="meta-dot" aria-hidden="true">·</span>
          <span v-if="s.era" class="meta-item">{{ s.era }}</span>
        </div>
      </el-card>
    </div>

    <el-empty v-if="!loading && !items.length" description="暂无匹配的简牍" />

    <div v-if="showCursorMore" class="cursor-more">
      <el-button :loading="loading" plain type="primary" @click="loadMoreCursor">
        继续载入更多
      </el-button>
    </div>

    <div v-if="total > size" class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        layout="total, prev, pager, next"
        :total="total"
      />
    </div>

    <el-drawer v-model="drawer" :title="detail?.code || '简牍详情'" size="420px" destroy-on-close>
      <el-skeleton v-if="detailLoading" :rows="8" animated />
      <template v-else-if="detail">
        <h3 class="dh">{{ detail.title }}</h3>
        <p class="dm"><span v-if="detail.site_name">出土地：{{ detail.site_name }}</span></p>
        <div v-if="slipImageSrc(detail.image_url)" class="drawer-fig">
          <img
            :src="slipImageSrc(detail.image_url)"
            :alt="`简牍影像 ${detail.code}`"
            class="drawer-img"
            loading="lazy"
          />
        </div>
        <el-divider content-position="left">释文</el-divider>
        <p class="body">{{ detail.transcription }}</p>
        <div class="row-btns">
          <el-button size="small" @click="copyText(detail.transcription)">复制释文</el-button>
        </div>
        <el-divider content-position="left">绎白</el-divider>
        <p class="body">{{ detail.vernacular }}</p>
        <div class="row-btns">
          <el-button size="small" @click="router.push('/slip/' + detail.id)">独立详情页（可分享）</el-button>
          <el-button type="primary" plain size="small" @click="markRead">记入掌阅</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 36px;
}
.browse-head {
  margin-bottom: 8px;
}
.page-kicker {
  margin-bottom: 6px;
}
.page-title {
  font-size: clamp(21px, 3vw, 26px);
  margin: 0 0 14px;
  letter-spacing: 0.08em;
  font-weight: 700;
}
.intro {
  margin: 0 0 10px;
  line-height: 1.88;
  color: var(--dj-ink-soft);
  font-size: 15px;
  max-width: 46em;
}
.intro-2 {
  margin: 0 0 20px;
  font-size: 13px;
  line-height: 1.75;
  color: var(--dj-bamboo);
  opacity: 0.95;
  max-width: 44em;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.search {
  flex: 1;
  min-width: 220px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.cell {
  cursor: pointer;
  transform-origin: center bottom;
  transition:
    transform 0.4s cubic-bezier(0.34, 1.45, 0.64, 1),
    box-shadow 0.35s ease,
    border-color 0.3s ease;
  will-change: transform;
}
.cell:hover {
  transform: translateY(-8px) scale(1.02);
  box-shadow:
    0 22px 44px rgba(42, 34, 24, 0.11),
    0 10px 24px rgba(124, 58, 33, 0.09),
    0 0 0 1px rgba(166, 124, 82, 0.2) !important;
}
.cell :deep(.el-card__body) {
  transition: background 0.35s ease;
}
.cell:hover :deep(.el-card__body) {
  background: linear-gradient(180deg, rgba(255, 252, 245, 0.98) 0%, rgba(252, 246, 234, 0.92) 100%) !important;
}
.code {
  font-family: var(--dj-font-display);
  font-weight: 700;
  color: var(--el-color-primary);
  font-size: 15px;
  margin-bottom: 6px;
}
.title {
  font-size: 14px;
  line-height: 1.5;
  color: var(--dj-ink);
  margin-bottom: 8px;
}
.meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--dj-bamboo);
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
  opacity: 0.96;
}
.meta-item {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta-dot {
  color: rgba(92, 107, 84, 0.55);
  user-select: none;
}
.cursor-more {
  margin: 12px 0 8px;
  display: flex;
  justify-content: center;
}
.pager {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
.dh {
  margin: 0 0 8px;
  font-size: 17px;
  font-family: var(--dj-font-display);
}
.dm {
  margin: 0;
  font-size: 13px;
  color: var(--dj-ink-soft);
}
.body {
  margin: 0;
  line-height: 1.8;
  font-size: 14px;
  color: var(--dj-ink);
  white-space: pre-wrap;
}
.row-btns {
  margin: 10px 0 16px;
}
.thumb-wrap {
  margin: 0 0 10px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--dj-border-light);
  background: #2a2218;
  max-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    transform 0.45s cubic-bezier(0.34, 1.45, 0.64, 1),
    box-shadow 0.35s ease,
    border-color 0.3s ease;
}
.cell:hover .thumb-wrap {
  transform: scale(1.04);
  box-shadow: 0 12px 28px rgba(42, 34, 24, 0.2);
  border-color: rgba(166, 124, 82, 0.35);
}
.thumb {
  max-width: 100%;
  max-height: 120px;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
  transition: transform 0.5s cubic-bezier(0.34, 1.45, 0.64, 1);
}
.cell:hover .thumb {
  transform: scale(1.03);
}

@media (prefers-reduced-motion: reduce) {
  .cell,
  .cell:hover,
  .thumb-wrap,
  .cell:hover .thumb-wrap,
  .thumb,
  .cell:hover .thumb {
    transition: none;
  }
  .cell:hover {
    transform: none;
  }
  .cell:hover .thumb-wrap,
  .cell:hover .thumb {
    transform: none;
  }
}
.drawer-fig {
  margin: 12px 0;
  text-align: center;
}
.drawer-img {
  max-width: 100%;
  max-height: 220px;
  object-fit: contain;
  border-radius: 4px;
  border: 1px solid var(--dj-border-light);
  background: #2a2218;
}
</style>
